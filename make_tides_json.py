#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional

import pdfplumber
import requests


# -----------------------------
# Config + Parsing helpers
# -----------------------------

MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}

# Typical day row:
# 1  0043 0.3  0612 2.7  1238 0.4  1849 2.8
# Be tolerant of spacing, 3/4-digit time, and 0.3 or 0.30
DAY_ROW_RE = re.compile(
    r"^\s*(\d{1,2})\s+"
    r"(\d{3,4})\s+([0-9]+\.[0-9]+)\s+"
    r"(\d{3,4})\s+([0-9]+\.[0-9]+)"
    r"(?:\s+(\d{3,4})\s+([0-9]+\.[0-9]+))?"
    r"(?:\s+(\d{3,4})\s+([0-9]+\.[0-9]+))?"
    r"\s*$"
)

def ztime(t: str) -> str:
    """Return HHMM (zero-padded)."""
    t = t.strip()
    return t.zfill(4)

def safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def download_pdf(url: str, out_path: str) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; reedys-big-tides/1.0)",
        "Accept": "application/pdf,*/*",
    }
    r = requests.get(url, timeout=60, headers=headers)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)


@dataclass(frozen=True)
class TideEvent:
    time_hhmm: str
    height_m: float


def parse_bom_pdf(pdf_path: str, base_year: int) -> Dict[str, List[TideEvent]]:
    """
    Parse BoM tide-table PDF into:
      key 'YYYY-MM-DD' -> [TideEvent(time_hhmm, height_m), ...]
    Handles:
      - multiple pages/month headings
      - year rollover when PDF includes Jan after Dec
      - rows with 2–4 events
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    data: Dict[str, List[TideEvent]] = {}

    current_month: Optional[int] = None
    current_year = base_year
    last_month_seen: Optional[int] = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Detect month headings; update month/year (handle rollover)
            for ln in lines:
                u = ln.upper()
                if u in MONTHS:
                    m = MONTHS[u]
                    # If we go from Dec (12) to Jan (1), increment year
                    if last_month_seen == 12 and m == 1:
                        current_year += 1
                    current_month = m
                    last_month_seen = m

            if not current_month:
                continue

            for ln in lines:
                m = DAY_ROW_RE.match(ln)
                if not m:
                    continue

                day_num = int(m.group(1))

                # Extract events (2 required, 2 optional)
                raw = [
                    (m.group(2), m.group(3)),
                    (m.group(4), m.group(5)),
                    (m.group(6), m.group(7)),
                    (m.group(8), m.group(9)),
                ]

                events: List[TideEvent] = []
                for t, h in raw:
                    if not t or not h:
                        continue
                    hf = safe_float(h)
                    if hf is None:
                        continue
                    events.append(TideEvent(ztime(t), hf))

                if len(events) < 2:
                    continue

                # Build date key safely
                try:
                    dkey = date(current_year, current_month, day_num).isoformat()
                except ValueError:
                    # Ignore impossible dates caused by text glitches
                    continue

                # Sort by time
                events.sort(key=lambda e: e.time_hhmm)

                # Append (do not overwrite) – some PDFs can duplicate lines across pages
                data.setdefault(dkey, [])
                existing = {(e.time_hhmm, e.height_m) for e in data[dkey]}
                for e in events:
                    if (e.time_hhmm, e.height_m) not in existing:
                        data[dkey].append(e)

                data[dkey].sort(key=lambda e: e.time_hhmm)

    return data


def classify_high_low(events: List[TideEvent]) -> List[Tuple[str, float, str]]:
    """
    Classify each event as 'low' or 'high' by local extrema in the sequence.
    Returns list of (time, height, kind).
    This is more robust than assuming low->high alternation always lines up.
    """
    if len(events) < 2:
        return []

    ev = sorted(events, key=lambda e: e.time_hhmm)

    heights = [e.height_m for e in ev]
    out: List[Tuple[str, float, str]] = []

    for i, e in enumerate(ev):
        if i == 0:
            kind = "low" if heights[i] <= heights[i + 1] else "high"
        elif i == len(ev) - 1:
            kind = "high" if heights[i] >= heights[i - 1] else "low"
        else:
            prev_h = heights[i - 1]
            next_h = heights[i + 1]
            if e.height_m <= prev_h and e.height_m <= next_h:
                kind = "low"
            elif e.height_m >= prev_h and e.height_m >= next_h:
                kind = "high"
            else:
                # Fallback: infer from slope
                kind = "high" if (e.height_m > prev_h) else "low"

        out.append((e.time_hhmm, round(e.height_m, 2), kind))

    return out


def build_low_to_high_pairs(events: List[TideEvent]) -> List[Dict[str, Any]]:
    """
    Build low->high pairs by:
      - classifying highs/lows
      - pairing each LOW with the next HIGH after it
    """
    classified = classify_high_low(events)
    if not classified:
        return []

    pairs: List[Dict[str, Any]] = []
    i = 0
    while i < len(classified):
        t, h, kind = classified[i]
        if kind != "low":
            i += 1
            continue

        # find next HIGH after this LOW
        j = i + 1
        while j < len(classified) and classified[j][2] != "high":
            j += 1
        if j >= len(classified):
            break

        t2, h2, _ = classified[j]
        if h2 <= h:
            i += 1
            continue

        pairs.append({
            "low_time": t,
            "low_m": round(h, 2),
            "high_time": t2,
            "high_m": round(h2, 2),
            "move_m": round(h2 - h, 2),
        })
        i = j + 1

    return pairs


def iso_today_local() -> str:
    return date.today().isoformat()


# -----------------------------
# Main generator
# -----------------------------

def main() -> None:
    # Inputs
    local_pdf = os.environ.get("LOCAL_PDF_PATH", "data/IDO59001_2026_VIC_TP013.pdf").strip()
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()

    # How far ahead to *consider* in output (use 45/60 so widget can show Top 10)
    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))

    # Optional filters (set to 0 to include all days)
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "0"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "0"))

    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    # Date window
    start = date.today()
    end = start + timedelta(days=days_ahead)

    # Ensure tmp dir
    os.makedirs("tmp", exist_ok=True)

    # Decide PDF source
    if os.path.exists(local_pdf):
        pdf_path = local_pdf
        source_pdf = local_pdf
    elif bom_pdf_url:
        pdf_path = "tmp/bom_tides.pdf"
        download_pdf(bom_pdf_url, pdf_path)
        source_pdf = bom_pdf_url
    else:
        raise SystemExit(f"Missing PDF source. Put PDF at '{local_pdf}' OR set BOM_PDF_URL.")

    # Parse PDF (base year = start.year; parser handles rollover)
    data = parse_bom_pdf(pdf_path, start.year)

    # Build all candidate days (not only "big tides" unless thresholds provided)
    days_out: List[Dict[str, Any]] = []

    d = start
    while d <= end:
        key = d.isoformat()
        events = data.get(key, [])
        if events:
            pairs = build_low_to_high_pairs(events)
            if pairs:
                max_high = max(p["high_m"] for p in pairs)
                max_move = max(p["move_m"] for p in pairs)

                # Include day if thresholds allow (or thresholds are 0)
                if (high_thr <= 0 or max_high >= high_thr) or (move_thr <= 0 or max_move >= move_thr):
                    days_out.append({
                        "date": key,
                        "pairs": pairs,
                        "max_high_m": round(max_high, 2),
                        "max_move_m": round(max_move, 2),
                    })
        d += timedelta(days=1)

    # Sort by biggest movement first (so your widget "Top 10 biggest" is naturally correct)
    days_out.sort(key=lambda x: x["max_move_m"], reverse=True)

    out = {
        "source": "Bureau of Meteorology (BoM) tide tables – Western Port (Stony Point)",
        "source_pdf": source_pdf,
        "timezone": tz_label,
        "generated_on": iso_today_local(),
        "days_ahead": days_ahead,
        "thresholds": {"high_m": high_thr, "move_m": move_thr},
        "days": days_out,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/tides.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote docs/tides.json with {len(days_out)} day(s) in window ({start} → {end}).")


if __name__ == "__main__":
    main()
