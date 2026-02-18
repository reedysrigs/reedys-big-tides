#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

# ----------------------------
# Config
# ----------------------------

# Check if the API key is being passed correctly
API_KEY = os.getenv("WORLD_TIDES_API_KEY")
if not API_KEY:
    print("ERROR: WORLD_TIDES_API_KEY is missing or not passed correctly")
    exit(1)
else:
    print("API Key is set properly ✅")

TZ_LABEL = os.environ.get("TZ_LABEL", "Australia/Melbourne").strip() or "Australia/Melbourne"
TZ = ZoneInfo(TZ_LABEL)

WP_CSV = os.environ.get("LOCAL_CSV_PATH", "data/westernport_tides_2026.csv").strip() or "data/westernport_tides_2026.csv"

OUT_FILE = "docs/tide-next.json"

SOURCE_WP = "BoM tide tables – Western Port (Stony Point)"
SOURCE_PPB = None  # later


# ----------------------------
# Data model
# ----------------------------

@dataclass(frozen=True)
class TideEvent:
    dt: datetime
    height_m: float


def _ztime(t: str) -> str:
    t = str(t).strip().replace(":", "")
    return t.zfill(4)


def _parse_iso_date(d: str) -> Optional[date]:
    try:
        return datetime.strptime(d.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _load_csv_events(path: str) -> List[TideEvent]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")

    out: List[TideEvent] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        req = {"date", "time", "height_m"}
        if not r.fieldnames or not req.issubset(set(r.fieldnames)):
            raise ValueError(f"CSV must have headers {sorted(req)}; got {r.fieldnames}")

        for row in r:
            ds = (row.get("date") or "").strip()
            ts = (row.get("time") or "").strip()
            hs = (row.get("height_m") or "").strip()
            if not ds or not ts or not hs:
                continue

            d = _parse_iso_date(ds)
            if not d:
                continue

            try:
                hm = float(hs)
            except Exception:
                continue

            hhmm = _ztime(ts)
            try:
                dt_naive = datetime.strptime(f"{d.isoformat()} {hhmm}", "%Y-%m-%d %H%M")
                dt_local = dt_naive.replace(tzinfo=TZ)
            except Exception:
                continue

            out.append(TideEvent(dt=dt_local, height_m=hm))

    out.sort(key=lambda e: e.dt)
    return out


def _classify_high_low(events: List[TideEvent]) -> List[tuple[TideEvent, str]]:
    """
    Classify events as "high" or "low" based on local extrema.
    Assumes events are in time order.
    """
    if len(events) < 2:
        return []

    ev = events
    vals = [e.height_m for e in ev]

    tagged: List[tuple[TideEvent, str]] = []
    for i, e in enumerate(ev):
        if i == 0:
            kind = "low" if vals[i] <= vals[i + 1] else "high"
        elif i == len(ev) - 1:
            kind = "high" if vals[i] >= vals[i - 1] else "low"
        else:
            if vals[i] <= vals[i - 1] and vals[i] <= vals[i + 1]:
                kind = "low"
            elif vals[i] >= vals[i - 1] and vals[i] >= vals[i + 1]:
                kind = "high"
            else:
                # fallback trend
                kind = "high" if vals[i] > vals[i - 1] else "low"

        tagged.append((e, kind))

    return tagged


def _next_kind_after(tagged: List[tuple[TideEvent, str]], now: datetime, kind: str) -> Optional[TideEvent]:
    for e, k in tagged:
        if e.dt > now and k == kind:
            return e
    return None


def _payload_for(events: List[TideEvent], now: datetime) -> Optional[dict]:
    tagged = _classify_high_low(events)
    if not tagged:
        return None

    nh = _next_kind_after(tagged, now, "high")
    nl = _next_kind_after(tagged, now, "low")

    if not nh and not nl:
        return None

    # range is absolute difference if both exist
    range_m: Optional[float] = None
    if nh and nl:
        range_m = round(abs(nh.height_m - nl.height_m), 2)

    return {
        "nextHighISO": nh.dt.isoformat() if nh else None,
        "nextLowISO": nl.dt.isoformat() if nl else None,
        "nextHigh_m": round(nh.height_m, 2) if nh else None,
        "nextLow_m": round(nl.height_m, 2) if nl else None,
        "range_m": range_m,
    }


def main() -> None:
    now = datetime.now(TZ)

    # Load all events, but only keep a small forward window (today + next 2 days)
    all_events = _load_csv_events(WP_CSV)
    cutoff = now + timedelta(days=3)
    wp_events = [e for e in all_events if now - timedelta(days=1) <= e.dt <= cutoff]

    out = {
        "timezone": TZ_LABEL,
        "generated_on": date.today().isoformat(),
        "wp": _payload_for(wp_events, now),
        "ppb": None,
        "source_wp": SOURCE_WP,
        "source_ppb": SOURCE_PPB,
    }

    os.makedirs("docs", exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
