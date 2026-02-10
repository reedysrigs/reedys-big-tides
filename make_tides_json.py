#!/usr/bin/env python3
import os
import re
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, Any

import requests
import pdfplumber

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12
}

# Matches tide rows like: "21  1040 0.73  1630 2.83  2230 0.55"
# Different BoM PDFs vary slightly, so we keep it flexible.
DAY_ROW_RE = re.compile(
    r"^\s*(\d{1,2})\s+"
    r"(\d{3,4})\s+([0-9.]+)\s+"
    r"(\d{3,4})\s+([0-9.]+)"
    r"(?:\s+(\d{3,4})\s+([0-9.]+))?"
    r"(?:\s+(\d{3,4})\s+([0-9.]+))?"
    r"\s*$"
)

def fmt_time(hhmm: str) -> str:
    hhmm = hhmm.zfill(4)
    return f"{hhmm[:2]}:{hhmm[2:]}"

def download(url: str, out_path: str) -> None:
    # Some gov sites dislike blank/unknown user agents. This helps.
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; reedys-big-tides/1.0)"
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

print("\n--- PAGE START ---")
print(text[:1200])
print("--- PAGE END ---\n")

lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Find month headings on page
            for ln in lines:
                if ln in MONTHS:
                    current_month = MONTHS[ln]

            if not current_month:
                continue

            # Parse day rows
            for ln in lines:
                m = DAY_ROW_RE.match(ln)
                if not m:
                    continue

                day = int(m.group(1))
                # First two events are always present in this pattern
                t1, h1 = m.group(2), float(m.group(3))
                t2, h2 = m.group(4), float(m.group(5))

                # Optional 3rd/4th events
                t3 = m.group(6); h3 = m.group(7)
                t4 = m.group(8); h4 = m.group(9)

                events: List[Tuple[str, float]] = [(t1.zfill(4), h1), (t2.zfill(4), h2)]
                if t3 and h3:
                    events.append((t3.zfill(4), float(h3)))
                if t4 and h4:
                    events.append((t4.zfill(4), float(h4)))

                # Build date key
                d = date(year, current_month, day).isoformat()
                data[d] = events

    return data

def build_low_to_high_pairs(events: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
    """
    Given daily tide events list [(time, height)...] in chronological order,
    build pairs of (LOW -> next HIGH).
    """
    pairs: List[Dict[str, Any]] = []
    if len(events) < 2:
        return pairs

    # Identify lows/highs by comparing neighboring heights.
    # Simpler: classify each event as low if it’s lower than both neighbors (where possible),
    # otherwise high. For the 2-event days, just treat smaller as low and larger as high.
    times = [t for t, _ in events]
    heights = [h for _, h in events]

    kinds: List[str] = []
    if len(events) == 2:
        kinds = ["low", "high"] if heights[0] < heights[1] else ["high", "low"]
    else:
        for i in range(len(heights)):
            prev_h = heights[i - 1] if i - 1 >= 0 else None
            next_h = heights[i + 1] if i + 1 < len(heights) else None
            h = heights[i]
            if prev_h is None:
                kinds.append("low" if next_h is not None and h < next_h else "high")
            elif next_h is None:
                kinds.append("low" if h < prev_h else "high")
            else:
                kinds.append("low" if (h < prev_h and h < next_h) else "high")

    # Pair low -> next high
    for i in range(len(events)):
        if kinds[i] != "low":
            continue
        low_t, low_h = events[i]
        # find next high after this low
        for j in range(i + 1, len(events)):
            if kinds[j] == "high":
                high_t, high_h = events[j]
                move = round(high_h - low_h, 2)
                pairs.append({
                    "low_time": fmt_time(low_t),
                    "low_m": round(low_h, 2),
                    "high_time": fmt_time(high_t),
                    "high_m": round(high_h, 2),
                    "move_m": move
                })
                break

    return pairs

def main():
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()
    if not bom_pdf_url:
        raise SystemExit("Missing BOM_PDF_URL. Set it as a GitHub repo VARIABLE.")

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

    out = {
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
        key = d.isoformat()  # IMPORTANT: keys are strings
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
