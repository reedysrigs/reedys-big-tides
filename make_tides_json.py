#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Any, Optional

import pdfplumber
import requests

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


# -----------------------------
# Month detection (FULL + ABBR)
# -----------------------------
MONTHS = {
    "JANUARY": 1, "JAN": 1,
    "FEBRUARY": 2, "FEB": 2,
    "MARCH": 3, "MAR": 3,
    "APRIL": 4, "APR": 4,
    "MAY": 5,
    "JUNE": 6, "JUN": 6,
    "JULY": 7, "JUL": 7,
    "AUGUST": 8, "AUG": 8,
    "SEPTEMBER": 9, "SEP": 9,
    "OCTOBER": 10, "OCT": 10,
    "NOVEMBER": 11, "NOV": 11,
    "DECEMBER": 12, "DEC": 12,
}

MONTH_YEAR_RE = re.compile(
    r"\b(" + "|".join(sorted(MONTHS.keys(), key=len, reverse=True)) + r")\b(?:\s+(\d{4}))?",
    re.IGNORECASE
)

TIME_RE = re.compile(r"^\d{3,4}$")


# -----------------------------
# Helpers
# -----------------------------
def melb_today(tz_label: str) -> date:
    if ZoneInfo is None:
        # Fallback: still works, but uses runner local (UTC)
        return datetime.utcnow().date()
    try:
        return datetime.now(ZoneInfo(tz_label)).date()
    except Exception:
        return datetime.utcnow().date()

def ztime(t: str) -> str:
    return t.strip().zfill(4)

def safe_height(token: str) -> Optional[float]:
    """
    BoM tables sometimes produce tokens with stray chars.
    Keep digits + dot only.
    """
    if token is None:
        return None
    s = "".join(ch for ch in token.strip() if (ch.isdigit() or ch == "."))
    if not s or s.count(".") > 1:
        return None
    try:
        return float(s)
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

def iso_today_local(tz_label: str) -> str:
    return melb_today(tz_label).isoformat()


@dataclass(frozen=True)
class TideEvent:
    time_hhmm: str
    height_m: float


# -----------------------------
# Parsing strategy A: extract_text tokens
# -----------------------------
def parse_from_text(pdf: pdfplumber.PDF, base_year: int) -> Dict[str, List[TideEvent]]:
    data: Dict[str, List[TideEvent]] = {}
    current_month: Optional[int] = None
    current_year: int = base_year
    last_month_seen: Optional[int] = None

    def set_month_from_line(line: str) -> None:
        nonlocal current_month, current_year, last_month_seen
        m = MONTH_YEAR_RE.search(line)
        if not m:
            return
        mon_txt = (m.group(1) or "").upper()
        yr_txt = (m.group(2) or "").strip()

        mnum = MONTHS.get(mon_txt)
        if not mnum:
            return

        if yr_txt.isdigit():
            current_year = int(yr_txt)
        elif last_month_seen == 12 and mnum == 1:
            current_year += 1

        current_month = mnum
        last_month_seen = mnum

    def add_event(dkey: str, t: str, h: float) -> None:
        data.setdefault(dkey, [])
        t2 = ztime(t)
        tup = (t2, round(h, 2))
        existing = {(e.time_hhmm, round(e.height_m, 2)) for e in data[dkey]}
        if tup not in existing:
            data[dkey].append(TideEvent(t2, h))

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for ln in lines:
            set_month_from_line(ln)

        if not current_month:
            continue

        for ln in lines:
            toks = ln.split()
            if not toks or not toks[0].isdigit():
                continue
            day_num = int(toks[0])
            if not (1 <= day_num <= 31):
                continue

            pairs: List[Tuple[str, float]] = []
            i = 1
            while i + 1 < len(toks):
                t = toks[i]
                htok = toks[i + 1]
                if TIME_RE.fullmatch(t):
                    hf = safe_height(htok)
                    if hf is not None:
                        pairs.append((ztime(t), hf))
                        i += 2
                        continue
                i += 1

            if len(pairs) < 2:
                continue

            try:
                dkey = date(current_year, current_month, day_num).isoformat()
            except ValueError:
                continue

            for t, h in pairs:
                add_event(dkey, t, h)

    for k in list(data.keys()):
        data[k] = sorted(data[k], key=lambda e: e.time_hhmm)

    return data


# -----------------------------
# Parsing strategy B: extract_tables fallback
# -----------------------------
def parse_from_tables(pdf: pdfplumber.PDF, base_year: int) -> Dict[str, List[TideEvent]]:
    data: Dict[str, List[TideEvent]] = {}
    current_month: Optional[int] = None
    current_year: int = base_year
    last_month_seen: Optional[int] = None

    def set_month_from_line(line: str) -> None:
        nonlocal current_month, current_year, last_month_seen
        m = MONTH_YEAR_RE.search(line)
        if not m:
            return
        mon_txt = (m.group(1) or "").upper()
        yr_txt = (m.group(2) or "").strip()
        mnum = MONTHS.get(mon_txt)
        if not mnum:
            return

        if yr_txt.isdigit():
            current_year = int(yr_txt)
        elif last_month_seen == 12 and mnum == 1:
            current_year += 1

        current_month = mnum
        last_month_seen = mnum

    def add_event(dkey: str, t: str, h: float) -> None:
        data.setdefault(dkey, [])
        t2 = ztime(t)
        tup = (t2, round(h, 2))
        existing = {(e.time_hhmm, round(e.height_m, 2)) for e in data[dkey]}
        if tup not in existing:
            data[dkey].append(TideEvent(t2, h))

    for page in pdf.pages:
        text = page.extract_text() or ""
        for ln in (l.strip() for l in text.splitlines() if l.strip()):
            set_month_from_line(ln)

        if not current_month:
            continue

        # Try extracting tables
        tables = page.extract_tables() or []
        for table in tables:
            for row in table:
                if not row:
                    continue
                # Row often: [day, time, height, time, height, ...] with blanks
                cells = [c.strip() for c in row if c and c.strip()]
                if not cells:
                    continue
                if not cells[0].isdigit():
                    continue
                day_num = int(cells[0])
                if not (1 <= day_num <= 31):
                    continue

                pairs: List[Tuple[str, float]] = []
                i = 1
                while i + 1 < len(cells):
                    t = cells[i]
                    htok = cells[i + 1]
                    if TIME_RE.fullmatch(t):
                        hf = safe_height(htok)
                        if hf is not None:
                            pairs.append((ztime(t), hf))
                            i += 2
                            continue
                    i += 1

                if len(pairs) < 2:
                    continue

                try:
                    dkey = date(current_year, current_month, day_num).isoformat()
                except ValueError:
                    continue

                for t, h in pairs:
                    add_event(dkey, t, h)

    for k in list(data.keys()):
        data[k] = sorted(data[k], key=lambda e: e.time_hhmm)

    return data


# -----------------------------
# Pair building (low -> next high)
# -----------------------------
def build_low_to_high_pairs(events: List[TideEvent]) -> List[Dict[str, Any]]:
    if len(events) < 2:
        return []

    ev = sorted(events, key=lambda e: e.time_hhmm)
    heights = [e.height_m for e in ev]

    classified: List[Tuple[str, float, str]] = []
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
                kind = "high" if e.height_m > prev_h else "low"
        classified.append((e.time_hhmm, round(e.height_m, 2), kind))

    pairs: List[Dict[str, Any]] = []
    i = 0
    while i < len(classified):
        t_low, h_low, kind = classified[i]
        if kind != "low":
            i += 1
            continue
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

    start = melb_today(tz_label)
    end = start + timedelta(days=days_ahead)

    os.makedirs("tmp", exist_ok=True)

    if os.path.exists(local_pdf):
        pdf_path = local_pdf
        source_pdf = local_pdf
    elif bom_pdf_url:
        pdf_path = "tmp/bom_tides.pdf"
        download_pdf(bom_pdf_url, pdf_path)
        source_pdf = bom_pdf_url
    else:
        raise SystemExit(f"Missing PDF source. Put PDF at '{local_pdf}' OR set BOM_PDF_URL.")

    print("=== ENV CHECK ===")
    print("START=", start)
    print("END=", end)
    print("DAYS_AHEAD=", days_ahead)
    print("HIGH_THRESHOLD=", high_thr)
    print("MOVE_THRESHOLD=", move_thr)
    print("TZ_LABEL=", tz_label)
    print("PDF=", pdf_path)
    print("=================")

    with pdfplumber.open(pdf_path) as pdf:
        # Try text parse first
        data = parse_from_text(pdf, start.year)
        print(f"[text] Parsed {len(data)} date keys.")

        # Fallback to tables if text parse looks broken
        if len(data) < 10:
            data2 = parse_from_tables(pdf, start.year)
            print(f"[tables] Parsed {len(data2)} date keys.")
            if len(data2) > len(data):
                data = data2

    if not data:
        raise SystemExit("ERROR: Parsed 0 date keys from PDF (text + tables). PDF may be image-only.")

    parsed_keys = sorted(data.keys())
    print(f"First key: {parsed_keys[0]} | Last key: {parsed_keys[-1]}")

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

                if (high_thr <= 0 or max_high >= high_thr) or (move_thr <= 0 or max_move >= move_thr):
                    days_out.append({
                        "date": key,
                        "pairs": pairs,
                        "max_high_m": round(max_high, 2),
                        "max_move_m": round(max_move, 2),
                    })
        d += timedelta(days=1)

    days_out.sort(key=lambda x: x["max_move_m"], reverse=True)

    out = {
        "source": "Bureau of Meteorology (BoM) tide tables – Western Port (Stony Point)",
        "source_pdf": source_pdf,
        "timezone": tz_label,
        "generated_on": iso_today_local(tz_label),
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
