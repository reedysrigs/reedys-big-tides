#!/usr/bin/env python3
import csv
import json
import os
import re
import requests
import pdfplumber
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional
import io

TZ = ZoneInfo("Australia/Melbourne")

# Western Port CSV (already in your repo)
WP_CSV = "data/westernport_tides_2026.csv"

# Williamstown (Port Phillip Bay)
PPB_PDF_URL = "https://www.bom.gov.au/ntc/IDO59001/IDO59001_2026_VIC_TP003.pdf"

OUT_FILE = "docs/tide-next.json"


@dataclass
class TideEvent:
    dt: datetime
    height: float


def now():
    return datetime.now(TZ)


def to_iso(dt: datetime):
    return dt.isoformat()


# ==============================
# WESTERN PORT (CSV)
# ==============================
def load_wp_events(path: str) -> List[TideEvent]:
    events = []
    if not os.path.exists(path):
        return events

    with open(path, "r", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            d = row.get("date", "").strip()
            t = row.get("time", "").strip().replace(":", "")
            h = row.get("height_m", "").strip()
            if not (d and t and h):
                continue
            try:
                dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H%M").replace(tzinfo=TZ)
                events.append(TideEvent(dt, float(h)))
            except:
                continue

    events.sort(key=lambda e: e.dt)
    return events


# ==============================
# PORT PHILLIP (PDF)
# ==============================
MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
    "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
    "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
}

TIME_HEIGHT = re.compile(r"^(\d{4})\s+(\d+\.\d+)$")


def load_ppb_events(url: str, year: int = 2026) -> List[TideEvent]:
    events = []
    resp = requests.get(url)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        month = None
        day = None

        for page in pdf.pages:
            lines = (page.extract_text() or "").split("\n")

            for line in lines:
                line = line.strip()

                if line in MONTHS:
                    month = MONTHS[line]
                    continue

                if line.isdigit() and len(line) <= 2:
                    day = int(line)
                    continue

                m = TIME_HEIGHT.match(line)
                if m and month and day:
                    hhmm = m.group(1)
                    height = float(m.group(2))
                    hh = int(hhmm[:2])
                    mm = int(hhmm[2:])
                    dt = datetime(year, month, day, hh, mm, tzinfo=TZ)
                    events.append(TideEvent(dt, height))

    events.sort(key=lambda e: e.dt)
    return events


# ==============================
# Find next high/low
# ==============================
def classify(events: List[TideEvent]):
    highs, lows = [], []
    for i in range(1, len(events)-1):
        if events[i].height >= events[i-1].height and events[i].height >= events[i+1].height:
            highs.append(events[i])
        if events[i].height <= events[i-1].height and events[i].height <= events[i+1].height:
            lows.append(events[i])
    return highs, lows


def next_after(events: List[TideEvent], t: datetime):
    for e in events:
        if e.dt > t:
            return e
    return None


def build_payload(events: List[TideEvent]):
    if not events:
        return None

    current = now()
    highs, lows = classify(events)

    nh = next_after(highs, current)
    nl = next_after(lows, current)

    if not (nh and nl):
        return None

    return {
        "nextHighISO": to_iso(nh.dt),
        "nextLowISO": to_iso(nl.dt),
        "nextHigh_m": round(nh.height, 2),
        "nextLow_m": round(nl.height, 2),
        "range_m": round(abs(nh.height - nl.height), 2)
    }


# ==============================
# MAIN
# ==============================
def main():
    out = {
        "timezone": "Australia/Melbourne",
        "generated_on": now().date().isoformat(),
        "wp": None,
        "ppb": None,
        "source_wp": "BoM Western Port CSV",
        "source_ppb": "BoM Williamstown PDF"
    }

    # Western Port
    try:
        wp_events = load_wp_events(WP_CSV)
        out["wp"] = build_payload(wp_events)
    except Exception as e:
        out["wp"] = None
        out["source_wp"] += f" (ERROR: {e})"

    # Port Phillip Bay
    try:
        ppb_events = load_ppb_events(PPB_PDF_URL)
        out["ppb"] = build_payload(ppb_events)
    except Exception as e:
        out["ppb"] = None
        out["source_ppb"] += f" (ERROR: {e})"

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
