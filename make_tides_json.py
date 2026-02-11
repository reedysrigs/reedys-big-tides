#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple


@dataclass(frozen=True)
class TideEvent:
    time_hhmm: str
    height_m: float


def ztime(t: str) -> str:
    t = t.strip()
    return t.zfill(4)


def iso_today_local() -> str:
    return date.today().isoformat()


def safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def load_csv(path: str) -> Dict[str, List[TideEvent]]:
    """
    Expects CSV columns:
      date,time,height_m
    where:
      date = YYYY-MM-DD
      time = HHMM (or HMM) (local time)
      height_m = metres
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")

    data: Dict[str, List[TideEvent]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"date", "time", "height_m"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must have headers: {sorted(required)}. Got: {reader.fieldnames}")

        for row in reader:
            d = (row.get("date") or "").strip()
            t = (row.get("time") or "").strip()
            h = (row.get("height_m") or "").strip()

            if not d or not t or not h:
                continue

            # validate date
            try:
                _ = datetime.strptime(d, "%Y-%m-%d")
            except Exception:
                continue

            hf = safe_float(h)
            if hf is None:
                continue

            data.setdefault(d, []).append(TideEvent(ztime(t), float(hf)))

    # sort each day
    for k in list(data.keys()):
        data[k] = sorted(data[k], key=lambda e: e.time_hhmm)

    return data


def build_low_to_high_pairs(events: List[TideEvent]) -> List[Dict[str, Any]]:
    """
    Pair each LOW with the next HIGH after it.
    """
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


def main() -> None:
    csv_path = os.environ.get("LOCAL_CSV_PATH", "data/stony_point_2026_tides.csv").strip()
    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "0"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "0"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    start = date.today()
    end = start + timedelta(days=days_ahead)

    data = load_csv(csv_path)
    keys = sorted(data.keys())
    print(f"Loaded {len(keys)} day keys from CSV.")
    if keys:
        print(f"First: {keys[0]} | Last: {keys[-1]}")

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
        "source_csv": csv_path,
        "timezone": tz_label,
        "generated_on": iso_today_local(),
        "days_ahead": days_ahead,
        "thresholds": {"high_m": high_thr, "move_m": move_thr},
        "days": days_out,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/tides.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote docs/tides.json with {len(days_out)} day(s) ({start} → {end}).")


if __name__ == "__main__":
    main()
