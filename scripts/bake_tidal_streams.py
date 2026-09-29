#!/usr/bin/env python3
"""
Predict tidal streams through enclosed-bay entrances and publish
docs/streams.json.

WHY THIS IS NOT THE OBVIOUS CALCULATION
---------------------------------------
The intuitive model - current follows how fast the tide height is changing -
is WRONG for a large bay behind a narrow entrance, and dangerously so. It
puts slack water at high and low tide. The Bureau says the opposite for
Port Phillip Heads:

    "Slack water occurs at about 3 hours before and after high water."
    "The ingoing stream runs from about 3 hours before to about 3 hours
     after high water."
    - BoM, Port Phillip Heads tidal stream notes

Port Phillip is too big to fill quickly through a 3 km gap, so the level
inside the bay lags the ocean outside by roughly three hours. Flow is driven
by the DIFFERENCE between inside and outside levels, and it peaks at high
water, not at mid-tide.

So the model here is: current is in phase with HEIGHT at the entrance.
  - peak ingoing  at high water
  - peak outgoing at low water
  - slack         midway in time between consecutive extremes
That reproduces BoM's stated 3-hour figure without assuming the interval is
exactly 6.2 hours, and it handles the diurnal inequality for free.

CONFIDENCE
----------
Timing comes straight from the Bureau and is solid. Rate is an ESTIMATE,
scaled from the spring peak by each tide's own range, and is published with
"rate_estimated": true. Nothing here is a substitute for the Bureau's own
predictions for navigation.
"""
import json, os, sys, math
import datetime as dt

OUT = "docs/streams.json"
HORIZON_DAYS = 7

# Only passages whose timing relationship is documented. A passage without a
# published figure does NOT get a guessed one - see README note.
PASSAGES = [
    {
        "id": "port-phillip-heads",
        "name": "Port Phillip Heads (The Rip)",
        "lat": -38.2939, "lon": 144.6170,
        "peak_kn_spring": 6.0,      # BoM: "up to 6 knots under normal conditions"
        "peak_kn_extreme": 9.0,     # BoM: "approaching 9 knots in extreme conditions"
        "timing_source": "BoM Port Phillip Heads tidal stream notes",
        "ingoing_dir": "into Port Phillip",
        "outgoing_dir": "out to Bass Strait",
    },
]


def fetch_extremes(lat, lon, key, days):
    """High/low water events from WorldTides. Returns [(datetime, height, type)]."""
    import requests
    start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=18)
    r = requests.get("https://www.worldtides.info/api/v3", timeout=40, params={
        "extremes": "", "lat": lat, "lon": lon,
        "start": int(start.timestamp()), "days": days + 1,
        "key": key,
    })
    r.raise_for_status()
    j = r.json()
    out = []
    for e in j.get("extremes", []):
        out.append((
            dt.datetime.fromtimestamp(e["dt"], dt.timezone.utc),
            float(e["height"]),
            "High" if str(e.get("type", "")).lower().startswith("h") else "Low",
        ))
    out.sort(key=lambda x: x[0])
    return out


def events_from_extremes(extremes, peak_spring, spring_range):
    """Turn high/low water into slack and peak-stream events.

    Pure function - no I/O - so it can be tested against BoM's stated figures.
    """
    ev = []
    for i, (t, h, kind) in enumerate(extremes):
        # peak stream at each extreme
        if i + 1 < len(extremes):
            rng = abs(extremes[i + 1][1] - h)
        elif i > 0:
            rng = abs(h - extremes[i - 1][1])
        else:
            rng = spring_range
        scale = rng / spring_range if spring_range > 0 else 1.0
        kn = round(max(0.5, min(peak_spring * 1.5, peak_spring * scale)), 1)
        ev.append({
            "at": t.isoformat(),
            "kind": "peak",
            "stream": "ingoing" if kind == "High" else "outgoing",
            "knots": kn,
            "tide": kind.lower(),
            "height_m": round(h, 2),
        })
        # slack midway in time to the next extreme
        if i + 1 < len(extremes):
            gap = (extremes[i + 1][0] - t).total_seconds()
            if 3 * 3600 < gap < 12 * 3600:      # ignore junk spacing
                ev.append({
                    "at": (t + dt.timedelta(seconds=gap / 2)).isoformat(),
                    "kind": "slack",
                    "turning": "to outgoing" if kind == "High" else "to ingoing",
                    "after_hw_h": round(gap / 7200, 1) if kind == "High" else None,
                })
    ev.sort(key=lambda e: e["at"])
    return ev


def main():
    key = os.environ.get("WORLD_TIDES_API_KEY", "").strip()
    if not key:
        print("FAILED: WORLD_TIDES_API_KEY is not set", file=sys.stderr)
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizon_days": HORIZON_DAYS,
        "note": ("Timing from the Bureau's published tidal stream relationship. "
                 "Rates are estimates scaled by tidal range. Not for navigation - "
                 "use the Bureau's own predictions for that."),
        "passages": [],
    }

    for p in PASSAGES:
        try:
            ext = fetch_extremes(p["lat"], p["lon"], key, HORIZON_DAYS)
        except Exception as e:
            print("FAILED: %s: %s" % (p["id"], e), file=sys.stderr)
            return 1
        if len(ext) < 4:
            print("FAILED: %s returned only %d extremes" % (p["id"], len(ext)), file=sys.stderr)
            return 1

        ranges = [abs(ext[i + 1][1] - ext[i][1]) for i in range(len(ext) - 1)]
        ranges.sort()
        spring = ranges[int(len(ranges) * 0.9)] if ranges else 1.0

        ev = events_from_extremes(ext, p["peak_kn_spring"], spring)
        nxt = [e for e in ev if e["at"] >= now.isoformat()]

        out["passages"].append({
            "id": p["id"], "name": p["name"],
            "lat": p["lat"], "lon": p["lon"],
            "ingoing_dir": p["ingoing_dir"], "outgoing_dir": p["outgoing_dir"],
            "peak_kn_spring": p["peak_kn_spring"],
            "peak_kn_extreme": p["peak_kn_extreme"],
            "timing_source": p["timing_source"],
            "rate_estimated": True,
            "spring_range_m": round(spring, 2),
            "events": nxt[:56],
        })
        print("%s: %d events, spring range %.2f m" % (p["id"], len(nxt), spring))

    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
