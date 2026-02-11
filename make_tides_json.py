#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional


@dataclass(frozen=True)
class TideEvent:
    time_hhmm: str
    height_m: float


def ztime(t: str) -> str:
    t = str(t).strip()
    t = t.replace(":", "")
    return t.zfill(4)


def valid_iso(d: str) -> bool:
    try:
        datetime.strptime(d, "%Y-%m-%d")
        return True
    except Exception:
        return False


def iso_today_local() -> str:
    return date.today().isoformat()


def load_csv(path: str) -> Dict[str, List[TideEvent]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")

    data: Dict[str, List[TideEvent]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        req = {"date", "time", "height_m"}
        if not reader.fieldnames or not req.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must have headers {sorted(req)}; got {reader.fieldnames}")

        for row in reader:
            d = (row.get("date") or "").strip()
            t = (row.get("time") or "").strip()
            h = (row.get("height_m") or "").strip()

            if not d or not t or not h:
                continue
            if not valid_iso(d):
                continue

            try:
                hf = float(h)
            except Exception:
                continue

            data.setdefault(d, []).append(TideEvent(ztime(t), float(hf)))

    for k in list(data.keys()):
        data[k] = sorted(data[k], key=lambda e: e.time_hhmm)
    return data


def build_low_to_high_moves(events: List[TideEvent]) -> List[dict]:
    # find LOW then next HIGH after it (based on height trend)
    if len(events) < 2:
        return []

    ev = sorted(events, key=lambda e: e.time_hhmm)
    h = [e.height_m for e in ev]

    classified = []
    for i, e in enumerate(ev):
        if i == 0:
            kind = "low" if h[i] <= h[i + 1] else "high"
        elif i == len(ev) - 1:
            kind = "high" if h[i] >= h[i - 1] else "low"
        else:
            if e.height_m <= h[i - 1] and e.height_m <= h[i + 1]:
                kind = "low"
            elif e.height_m >= h[i - 1] and e.height_m >= h[i + 1]:
                kind = "high"
            else:
                kind = "high" if e.height_m > h[i - 1] else "low"
        classified.append((e.time_hhmm, round(e.height_m, 2), kind))

    moves = []
    i = 0
    while i < len(classified):
        t1, v1, k1 = classified[i]
        if k1 != "low":
            i += 1
            continue

        j = i + 1
        while j < len(classified) and classified[j][2] != "high":
            j += 1
        if j >= len(classified):
            break

        t2, v2, _ = classified[j]
        if v2 > v1:
            moves.append({
                "low_time": t1,
                "low_m": v1,
                "high_time": t2,
                "high_m": v2,
                "move_m": round(v2 - v1, 2),
            })
        i = j + 1

    return moves


def main() -> None:
    csv_path = os.environ.get("LOCAL_CSV_PATH", "data/westernport_tides_2026.csv").strip()
    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    start = date.today()
    end = start + timedelta(days=days_ahead)

    data = load_csv(csv_path)

    days_out: List[dict] = []
    d = start
    while d <= end:
        key = d.isoformat()
        events = data.get(key, [])
        if events:
            moves = build_low_to_high_moves(events)
            if moves:
                max_move = max(m["move_m"] for m in moves)
                days_out.append({
                    "date": key,
                    "moves": moves,
                    "max_move_m": round(max_move, 2),
                })
        d += timedelta(days=1)

    # Top 10 biggest moves in the next N days
    top10 = sorted(days_out, key=lambda x: x["max_move_m"], reverse=True)[:10]

    out = {
        "source": "BoM tide tables – Western Port (Stony Point)",
        "source_csv": csv_path,
        "timezone": tz_label,
        "generated_on": iso_today_local(),
        "days_ahead": days_ahead,
        "top10": top10
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/tides.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote docs/tides.json with top10={len(top10)} (window {start} → {end}).")


if __name__ == "__main__":
    main()
