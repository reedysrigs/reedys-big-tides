#!/usr/bin/env python3
import os, json, time
from datetime import datetime, timezone
import requests

OUT_PATH = "../docs/tide-next.json"

# Williamstown (Port Phillip Bay)
PPB_LAT = -37.8620
PPB_LON = 144.8890

WORLD_TIDES = "https://www.worldtides.info/api/v3"

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def next_high_low(extremes):
    now = time.time()
    next_high = None
    next_low = None
    hH = None
    hL = None

    for e in extremes:
        iso = e.get("date")
        typ = (e.get("type") or "").lower()
        h = e.get("height")

        if not iso or h is None:
            continue

        t = datetime.fromisoformat(iso).timestamp()
        if t <= now:
            continue

        if typ == "high" and next_high is None:
            next_high = iso
            hH = float(h)

        if typ == "low" and next_low is None:
            next_low = iso
            hL = float(h)

        if next_high and next_low:
            break

    range_m = None
    if hH is not None and hL is not None:
        range_m = round(abs(hH - hL), 2)

    return {
        "nextHighISO": next_high,
        "nextLowISO": next_low,
        "range_m": range_m
    }

def main():
    key = os.getenv("WORLDTIDES_API_KEY")
    if not key:
        raise SystemExit("Missing WORLDTIDES_API_KEY")

    r = requests.get(WORLD_TIDES, params={
        "extremes": "",
        "date": "today",
        "days": 2,
        "localtime": "",
        "lat": PPB_LAT,
        "lon": PPB_LON,
        "stationDistance": 10,
        "key": key
    }, timeout=20)

    r.raise_for_status()
    data = r.json()

    if int(data.get("status", 0)) != 200:
        raise SystemExit(f"WorldTides error: {data.get('error')}")

    ppb = next_high_low(data.get("extremes") or [])

    # Keep existing WP block if present
    wp = {}
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
            wp = existing.get("wp") or {}
    except Exception:
        pass

    out = {
        "generated_utc": utc_now(),
        "ppb": ppb,
        "wp": wp
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")

    print("tide-next.json updated")

if __name__ == "__main__":
    main()
