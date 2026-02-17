#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple


TZ_LABEL = "Australia/Melbourne"

# ---- CHANGE THESE TWO FILE PATHS IF NEEDED ----
WP_CSV  = "data/westernport_tides_2026_FULL.csv"
PPB_CSV = "data/portphillip_tides_2026.csv"
# ----------------------------------------------


@dataclass(frozen=True)
class TideEvent:
    dt: datetime
    height_m: float


def load_csv_events(path: str) -> List[TideEvent]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    out: List[TideEvent] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)

        for row in r:
            d = (row.get("date") or "").strip()
            t = (row.get("time") or "").strip()
            h = (row.get("height_m") or "").strip()

            if not (d and t and h):
                continue

            try:
                hhmm = t.replace(":", "").zfill(4)
                dt = datetime.strptime(f"{d} {hhmm}", "%Y-%m-%d %H%M")
                out.append(TideEvent(dt=dt, height_m=float(h)))
            except Exception:
                continue

    out.sort(key=lambda e: e.dt)
    return out


def classify_extremes(events: List[TideEvent]) -> List[Tuple[str, TideEvent]]:
    if len(events) < 2:
        return []

    ext: List[Tuple[str, TideEvent]] = []

    for i, e in enumerate(events):
        prev_h = events[i-1].height_m if i > 0 else None
        next_h = events[i+1].height_m if i < len(events)-1 else None

        if prev_h is None:
            kind = "low" if e.height_m <= next_h else "high"
        elif next_h is None:
            kind = "high" if e.height_m >= prev_h else "low"
        else:
            if e.height_m <= prev_h and e.height_m <= next_h:
                kind = "low"
            elif e.height_m >= prev_h and e.height_m >= next_h:
                kind = "high"
            else:
                kind = "high" if e.height_m > prev_h else "low"

        ext.append((kind, e))

    cleaned: List[Tuple[str, TideEvent]] = []
    for kind, e in ext:
        if not cleaned or cleaned[-1][0] != kind:
            cleaned.append((kind, e))
        else:
            prev_kind, prev_e = cleaned[-1]
            if kind == "high" and e.height_m > prev_e.height_m:
                cleaned[-1] = (kind, e)
            if kind == "low" and e.height_m < prev_e.height_m:
                cleaned[-1] = (kind, e)

    return cleaned


def next_turns(events: List[TideEvent], now: datetime) -> Optional[dict]:
    look_ahead = now + timedelta(hours=48)
    future = [e for e in events if now <= e.dt <= look_ahead]

    if len(future) < 3:
        return None

    turns = classify_extremes(future)

    next_high = next((e for kind, e in turns if kind == "high" and e.dt >= now), None)
    next_low  = next((e for kind, e in turns if kind == "low" and e.dt >= now), None)

    if not next_high or not next_low:
        return None

    rng = abs(next_high.height_m - next_low.height_m)

    return {
        "nextHighISO": next_high.dt.strftime("%Y-%m-%dT%H:%M:00+11:00"),
        "nextLowISO":  next_low.dt.strftime("%Y-%m-%dT%H:%M:00+11:00"),
        "nextHigh_m": round(next_high.height_m, 2),
        "nextLow_m":  round(next_low.height_m, 2),
        "range_m":    round(rng, 2)
    }


def main():
    now = datetime.now()

    wp_events  = load_csv_events(WP_CSV)
    ppb_events = load_csv_events(PPB_CSV)

    out = {
        "timezone": TZ_LABEL,
        "generated_on": date.today().isoformat(),
        "wp":  next_turns(wp_events, now),
        "ppb": next_turns(ppb_events, now)
    }

    os.makedirs("docs", exist_ok=True)

    with open("docs/tide-next.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("Wrote docs/tide-next.json")


if __name__ == "__main__":
    main()

