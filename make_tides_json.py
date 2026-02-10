#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import json
from datetime import date, timedelta
from typing import Dict, List, Tuple, Any

import requests
import pdfplumber

# Map month headings found in the BoM PDF to month numbers
MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
    "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
    "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
}

# Example line pattern (varies a bit by PDF extraction):
#  1   0123 0.45  0744 2.11  1330 0.62  2010 2.05
# Day  t1   h1    t2   h2    t3   h3    t4   h4
DAY_ROW_RE = re.compile(
    r"^\s*(\d{1,2})\s+"
    r"(\d{3,4})\s+([0-9.]+)\s+"
    r"(\d{3,4})\s+([0-9.]+)"
    r"(?:\s+(\d{3,4})\s+([0-9.]+))?"
    r"(?:\s+(\d{3,4})\s+([0-9.]+))?"
    r"\s*$"
)

def download(url: str, out_path: str) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; reedys-big-tides/1.0; +https://github.com/reedysrigs/reedys-big-tides)"
    }
    r = requests.get(url, timeout=60, headers=headers)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)

def parse_bom_pdf(pdf_path: str, year: int) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns dict keyed by 'YYYY-MM-DD' -> list of (time 'HHMM', height_m).
    """
    data: Dict[str, List[Tuple[str, float]]] = {}
    current_month: int | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Find month headings on page (JANUARY, FEBRUARY, etc)
            for ln in lines:
                up = ln.upper()
                if up in MONTHS:
                    current_month = MONTHS[up]

            if not current_month:
                continue

            # Parse day rows
            for ln in lines:
                m = DAY_ROW_RE.match(ln)
                if not m:
                    continue

                day = int(m.group(1))

                # First two events always present
                t1, h1 = m.group(2), float(m.group(3))
                t2, h2 = m.group(4), float(m.group(5))

                events: List[Tuple[str, float]] = [(t1.zfill(4), h1), (t2.zfill(4), h2)]

                # Optional 3rd/4th
                t3, h3 = m.group(6), m.group(7)
                t4, h4 = m.group(8), m.group(9)
                if t3 and h3:
                    events.append((t3.zfill(4), float(h3)))
                if t4 and h4:
                    events.append((t4.zfill(4), float(h4)))

                key = date(year, current_month, day).isoformat()
                data[key] = events

    return data

def build_low_to_high_pairs(events: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
    """
    Given a day's events [(time, height)...], build low->high pairs by scanning in time order.
    We treat a "pair" as any rising segment from a local min to subsequent local max.
    """
    if not events:
        return []

    # sort by time (HHMM string)
    ev = sorted(events, key=lambda x: x[0])

    pairs: List[Dict[str, Any]] = []
    # simple approach: pair consecutive events if second is higher (rise)
    for i in range(len(ev) - 1):
        t1, h1 = ev[i]
        t2, h2 = ev[i + 1]
        if h2 > h1:
            pairs.append({
                "low_time": t1,
                "low_m": round(h1, 2),
                "high_time": t2,
                "high_m": round(h2, 2),
                "move_m": round(h2 - h1, 2),
            })

    return pairs

def main() -> None:
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()
    if not bom_pdf_url:
        raise SystemExit("Missing BOM_PDF_URL. Set it as a GitHub repo variable.")

    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "2.8"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "2.2"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    today = date.today()
    end = today + timedelta(days=days_ahead)
    year = today.year

    os.makedirs("tmp", exist_ok=True)
    pdf_path = "tmp/bom_tides.pdf"
    download(bom_pdf_url, pdf_path)

    data = parse_bom_pdf(pdf_path, year)

    out: Dict[str, Any] = {
        "source": "Bureau of Meteorology (BoM) tide tables – Western Port (Stony Point)",
        "source_pdf": bom_pdf_url,
        "timezone": tz_label,
        "generated_on": today.isoformat(),
        "days_ahead": days_ahead,
        "thresholds": {"high_m": high_thr, "move_m": move_thr},
        "days": []
    }

    d = today
    while d <= end:
        key = d.isoformat()
        events = data.get(key)
        if events:
            pairs = build_low_to_high_pairs(events)
            if pairs:
                max_high = max(p["high_m"] for p in pairs)
                max_move = max(p["move_m"] for p in pairs)
                if (max_high >= high_thr) or (max_move >= move_thr):
                    out["days"].append({
                        "date": key,
                        "pairs": pairs,
                        "max_high_m": round(max_high, 2),
                        "max_move_m": round(max_move, 2)
                    })
        d += timedelta(days=1)

    os.makedirs("docs", exist_ok=True)
    with open("docs/tides.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote docs/tides.json with {len(out['days'])} big-tide day(s).")

if __name__ == "__main__":
    main()
