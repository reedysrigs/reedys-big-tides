#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from datetime import date, timedelta
from typing import Dict, List, Any


CSV_PATH = "data/stony_point_2026_tides.csv"
OUT_JSON = "docs/tides.json"


def build_low_to_high_pairs(events):
    """
    events: list of (time, height) sorted by time
    """
    pairs = []
    for i in range(len(events) - 1):
        t1, h1 = events[i]
        t2, h2 = events[i + 1]
        if h2 > h1:
            pairs.append({
                "low_time": t1,
                "low_m": round(h1, 2),
                "high_time": t2,
                "high_m": round(h2, 2),
                "move_m": round(h2 - h1, 2),
            })
    return pairs


def main():
    days_ahead = int(os.getenv("DAYS_AHEAD", "60"))
    start = date.today()
    end = start + timedelta(days=days_ahead)

    # Load CSV
    daily: Dict[str, List[tuple]] = {}
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d = r["date"]
            t = r["time"].zfill(4)
            h = float(r["height_m"])
            daily.setdefault(d, []).append((t, h))

    # Build output days
    days_out: List[Dict[str, Any]] = []

    for d in sorted(daily.keys()):
        d_date = date.fromisoformat(d)
        if not (start <= d_date <= end):
            continue

        events = sorted(daily[d], key=lambda x: x[0])
        pairs = build_low_to_high_pairs(events)
        if not pairs:
            continue

        max_high = max(p["high_m"] for p in pairs)
        max_move = max(p["move_m"] for p in pairs)

        days_out.append({
            "date": d,
            "pairs": pairs,
            "max_high_m": round(max_high, 2),
            "max_move_m": round(max_move, 2),
        })

    # Sort biggest movement first
    days_out.sort(key=lambda x: x["max_move_m"], reverse=True)

    out = {
        "source": "BoM tide tables – Western Port (Stony Point)",
        "source_csv": CSV_PATH,
        "timezone": "Australia/Melbourne",
        "generated_on": start.isoformat(),
        "days_ahead": days_ahead,
        "thresholds": {"high_m": 0, "move_m": 0},
        "days": days_out,
    }

    os.makedirs("docs", exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote {len(days_out)} days to {OUT_JSON}")


if __name__ == "__main__":
    main()

