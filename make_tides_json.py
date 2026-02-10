#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Tuple, Any, Optional

import pdfplumber
import requests


# -----------------------------
# Constants
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

MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS.keys()) + r")\b", re.IGNORECASE)
TIME_RE = re.compile(r"^\d{3,4}$")
FLOAT_RE = re.compile(r"^[0-9]+\.[0-9]+$")


# -----------------------------
# Helpers
# -----------------------------

def ztime(t: str) -> str:
    return t.strip().zfill(4)

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

def iso_today_local() -> str:
    return date.today().isoformat()


@dataclass(frozen=True)
class TideEvent:
    time_hhmm: str
    height_m: float


# -----------------------------
# PDF Parsing (robust)
# -----------------------------

def parse_bom_pdf(pdf_path: str, base_year: int) -> Dict[str, List[TideEvent]]:
    """
    Robustly parse a BoM tide-table PDF into:
      'YYYY-MM-DD' -> list[TideEvent(time_hhmm, height_m)]

    Why this works:
    - BoM PDFs often extract text with odd spacing/columns.
    - Token parsing is far more reliable than matching an entire line with a strict regex.
    - Month can appear inside headings like "FEBRUARY 2026" etc.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    data: Dict[str, List[TideEvent]] = {}

    current_month: Optional[int] = None
    current_year = base_year
    last_month_seen: Optional[int] = None

    def set_month_from_line(line: str) -> None:
        nonlocal current_month, current_year, last_month_seen
        m = MONTH_RE.search(line)
        if not m:
            return
        mon = m.group(1).upper()
        mnum = MONTHS.get(mon)
        if not mnum:
            return

        # Handle rollover: Dec -> Jan means year +1
        if last_month_seen == 12 and mnum == 1:
            current_year += 1

        current_month = mnum
        last_month_seen = mnum

    def add_event(dkey: str, t: str, h: float) -> None:
        data.setdefault(dkey, [])
        t = ztime(t)
        h = float(h)
        tup = (t, round(h, 2))
        existing = {(e.time_hhmm, round(e.height_m, 2)) for e in data[dkey]}
        if tup not in existing:
            data[dkey].append(TideEvent(t, h))

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Month detection first (anywhere in any line)
            for ln in lines:
                set_month_from_line(ln)

            if not current_month:
                continue

            # Parse day rows by tokens:
            # Expect a row beginning with day number, followed by (time height) pairs.
            for ln in lines:
                toks = ln.split()
                if not toks:
                    continue

                if not toks[0].isdigit():
                    continue

                day_num = int(toks[0])
                if not (1 <= day_num <= 31):
                    continue

                # Gather time/height pairs from remaining tokens
                pairs: List[Tuple[str, float]] = []
                i = 1
                while i + 1 < len(toks):
                    t = toks[i]
                    h = toks[i + 1]

                    if TIME_RE.fullmatch(t) and FLOAT_RE.fullmatch(h):
                        hf = safe_float(h)
                        if hf is not None:
                            pairs.append((ztime(t), hf))
                            i += 2
                            continue
                    i += 1

                # Need at least 2 events to be useful
                if len(pairs) < 2:
                    continue

                # Build date key
                try:
                    dkey = date(current_year, current_month, day_num).isoformat()
                except ValueError:
                    continue

                for t, h in pairs:
                    add_event(dkey, t, h)

    # Sort each day’s events by time
    for k in list(data.keys()):
        data[k] = sorted(data[k], key=lambda e: e.time_hhmm)

    return data


# -----------------------------
# Pair building (low -> next high)
# -----------------------------

def build_low_to_high_pairs(events: List[TideEvent]) -> List[Dict[str, Any]]:
    """
    Turn daily events into low->high pairs.

    Strategy:
    - Sort by time
    - Determine which points are "lows" vs "highs" via local extrema
    - Pair each LOW with the next HIGH after it
    """
    if len(events) < 2:
        return []

    ev = sorted(events, key=lambda e: e.time_hhmm)

    # classify each as low/high using local extrema
    classified: List[Tuple[str, float, str]] = []
    heights = [e.height_m for e in ev]

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
                # fallback
                kind = "high" if e.height_m > prev_h else "low"

        classified.append((e.time_hhmm, round(e.height_m, 2), kind))

    pairs: List[Dict[str, Any]] = []
    i = 0
    while i < len(classified):
        t_low, h_low, kind = classified[i]
        if kind != "low":
            i += 1
            continue

        # find next high after it
        j = i + 1
        while j < len(classified) and classified[j][2] != "high":
            j += 1
        if j >= len(classified):
            break

        t_high, h_high, _ = classified[j]
        if h_high <= h_low:
            i += 1
            continue

        pairs.append({
            "low_time": t_low,
            "low_m": round(h_low, 2),
            "high_time": t_high,
            "high_m": round(h_high, 2),
            "move_m": round(h_high - h_low, 2),
        })
        i = j + 1

    return pairs


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    local_pdf = os.environ.get("LOCAL_PDF_PATH", "data/IDO59001_2026_VIC_TP013.pdf").strip()
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()

    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "0"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "0"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    start = date.today()
    end = start + timedelta(days=days_ahead)

    os.makedirs("tmp", exist_ok=True)

    # PDF source selection
    if os.path.exists(local_pdf):
        pdf_path = local_pdf
        source_pdf = local_pdf
    elif bom_pdf_url:
        pdf_path = "tmp/bom_tides.pdf"
        download_pdf(bom_pdf_url, pdf_path)
        source_pdf = bom_pdf_url
    else:
        raise SystemExit(f"Missing PDF source. Put PDF at '{local_pdf}' OR set BOM_PDF_URL.")

    # Parse PDF
    data = parse_bom_pdf(pdf_path, start.year)

    # Debug summary (helps immediately in Actions log)
    # Count all parsed day keys and the next 120 days available
    parsed_keys = sorted(data.keys())
    print(f"Parsed {len(parsed_keys)} date keys from PDF.")
    if parsed_keys:
        print(f"First key: {parsed_keys[0]}  |  Last key: {parsed_keys[-1]}")

    # Build output for requested window
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

                # Thresholds: set to 0 in workflow to include all days
                if (high_thr <= 0 or max_high >= high_thr) or (move_thr <= 0 or max_move >= move_thr):
                    days_out.append({
                        "date": key,
                        "pairs": pairs,
                        "max_high_m": round(max_high, 2),
                        "max_move_m": round(max_move, 2),
                    })
        d += timedelta(days=1)

    # Sort by biggest movement (site takes Top 10)
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
