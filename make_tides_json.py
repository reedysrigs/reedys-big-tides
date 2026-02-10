#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import json
from datetime import date, timedelta
from typing import Dict, List, Tuple, Any, Optional

import pdfplumber
import requests

# Month headings that appear in the BoM tide-table PDFs
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

# Typical day row looks like:
# "1  0043 0.3  0612 2.7  1238 0.4  1849 2.8"
# Some PDFs vary spacing; this is tolerant.
DAY_ROW_RE = re.compile(
    r"^\s*(\d{1,2})\s+"
    r"(\d{3,4})\s+([0-9]+\.[0-9]+)\s+"
    r"(\d{3,4})\s+([0-9]+\.[0-9]+)"
    r"(?:\s+(\d{3,4})\s+([0-9]+\.[0-9]+))?"
    r"(?:\s+(\d{3,4})\s+([0-9]+\.[0-9]+))?"
    r"\s*$"
)

def download(url: str, out_path: str) -> None:
    """
    Download a PDF to out_path.
    NOTE: BoM may block bot downloads. Best practice is to use a local repo PDF,
    or use a GitHub raw URL you control.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; reedys-big-tides/1.0)",
        "Accept": "application/pdf,*/*",
    }
    r = requests.get(url, timeout=60, headers=headers)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)

def parse_bom_pdf(pdf_path: str, year: int) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns dict keyed by 'YYYY-MM-DD' -> list of (time 'HHMM', height_m).
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    data: Dict[str, List[Tuple[str, float]]] = {}
    current_month: Optional[int] = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Update current_month when we see a month heading on this page
            for ln in lines:
                u = ln.upper()
                if u in MONTHS:
                    current_month = MONTHS[u]

            if not current_month:
                continue

            # Parse day rows
            for ln in lines:
                m = DAY_ROW_RE.match(ln)
                if not m:
                    continue

                day = int(m.group(1))

                # Required two events
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

                # Build date key
                try:
                    dkey = date(year, current_month, day).isoformat()
                except ValueError:
                    # Skip impossible dates (rare OCR/text glitches)
                    continue

                # Sort by time just in case
                events.sort(key=lambda x: x[0])

                data[dkey] = events

    return data

def build_low_to_high_pairs(events: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
    """
    Convert daily tide events into low->high pairs.
    We try to find each LOW then the next HIGH after it.
    """
    if not events or len(events) < 2:
        return []

    ev = sorted(events, key=lambda x: x[0])
    pairs: List[Dict[str, Any]] = []

    i = 0
    while i < len(ev) - 1:
        t_a, h_a = ev[i]
        t_b, h_b = ev[i + 1]

        # If rising, treat as low->high
        if h_b > h_a:
            pairs.append({
                "low_time": t_a,
                "low_m": round(h_a, 2),
                "high_time": t_b,
                "high_m": round(h_b, 2),
                "move_m": round(h_b - h_a, 2),
            })
            i += 2
        else:
            # Not rising: skip forward until we hit a low->high rise
            i += 1

    return pairs

def main() -> None:
    # Prefer local PDF in the repo (your current setup)
    local_pdf = os.environ.get("LOCAL_PDF_PATH", "data/IDO59001_2026_VIC_TP013.pdf").strip()

    # Optional: if you ever want to use a URL (best: GitHub raw URL you control)
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()

    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "2.8"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "2.2"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    today = date.today()
    end = today + timedelta(days=days_ahead)
    year = today.year

    os.makedirs("tmp", exist_ok=True)

    # Decide PDF source
    if os.path.exists(local_pdf):
        pdf_path = local_pdf
    elif bom_pdf_url:
        pdf_path = "tmp/bom_tides.pdf"
        download(bom_pdf_url, pdf_path)
    else:
        raise SystemExit(
            f"Missing PDF source. Put the PDF at '{local_pdf}' OR set BOM_PDF_URL."
        )

    data = parse_bom_pdf(pdf_path, year)

    out = {
        "source": "Bureau of Meteorology (BoM) tide tables – Western Port (Stony Point)",
        "source_pdf": bom_pdf_url if bom_pdf_url else local_pdf,
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
