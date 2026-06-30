import os
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# --- Config -----------------------------------------------------------------
API_KEY = "5fee6eb9-5c05-41f7-89d9-918e3961b35d"
MEL = ZoneInfo("Australia/Melbourne")

FETCH_DAYS = 33      # how far ahead to request (buffer beyond the 30-day window)
WINDOW_DAYS = 30     # only keep days within the next 30 days
TOP_N = 10           # biggest-movement days to output

# One entry per bay. PPB tide range is much smaller than Western Port — that's
# expected. If you want PPB referenced to a specific spot (the Heads, Williamstown,
# Geelong etc.), just change this lat/lon and re-run; WorldTides snaps to the
# nearest tide station.
BAYS = {
    "wp":  {"lat": -38.37, "lon": 145.22, "out": "docs/tides.json",     "tide_next": True},
    "ppb": {"lat": -38.00, "lon": 144.85, "out": "docs/tides-ppb.json", "tide_next": False},
}

now_utc = datetime.now(timezone.utc)
start = int(now_utc.timestamp())
length = FETCH_DAYS * 86400          # WorldTides uses 'length' in SECONDS, NOT 'end'
cutoff = now_utc + timedelta(days=WINDOW_DAYS)
now_ms = now_utc.timestamp()


def fetch_extremes(lat, lon):
    url = (
        "https://www.worldtides.info/api/v3"
        f"?extremes&lat={lat}&lon={lon}"
        f"&start={start}&length={length}"
        f"&key={API_KEY}"
    )
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    return res.json().get("extremes", [])


def build_top10(extremes):
    """Biggest Low<->High swing per day, top N days by size, within the window."""
    day_best = {}
    for i in range(len(extremes) - 1):
        a = extremes[i]
        b = extremes[i + 1]
        if {a["type"], b["type"]} != {"Low", "High"}:
            continue
        low  = a if a["type"] == "Low"  else b
        high = a if a["type"] == "High" else b
        low_dt  = datetime.fromtimestamp(low["dt"],  MEL)
        high_dt = datetime.fromtimestamp(high["dt"], MEL)
        earlier = min(low_dt, high_dt)
        if earlier > cutoff.astimezone(MEL):
            continue
        move = round(high["height"] - low["height"], 2)
        date_str = earlier.strftime("%Y-%m-%d")
        swing = {
            "date": date_str,
            "moves": [{
                "low_time":  low_dt.strftime("%H%M"),
                "low_m":     round(low["height"], 2),
                "high_time": high_dt.strftime("%H%M"),
                "high_m":    round(high["height"], 2),
                "move_m":    move,
            }],
            "max_move_m": move,
        }
        if date_str not in day_best or move > day_best[date_str]["max_move_m"]:
            day_best[date_str] = swing
    return sorted(day_best.values(), key=lambda x: x["max_move_m"], reverse=True)[:TOP_N]


def build_tide_next(extremes):
    """Next high / next low / range — used by the Fishing Window WP tab."""
    def first_future(kind):
        cands = [e for e in extremes if e.get("type") == kind and e.get("dt", 0) >= now_ms]
        cands.sort(key=lambda e: e["dt"])
        return cands[0] if cands else None

    next_high = first_future("High")
    next_low  = first_future("Low")

    def iso(e):
        return datetime.fromtimestamp(e["dt"], MEL).isoformat() if e else None

    range_m = round(abs(next_high["height"] - next_low["height"]), 2) if (next_high and next_low) else None
    return {
        "nextHighISO": iso(next_high),
        "nextLowISO":  iso(next_low),
        "nextHigh_m":  round(next_high["height"], 2) if next_high else None,
        "nextLow_m":   round(next_low["height"], 2) if next_low else None,
        "range_m":     range_m,
    }


os.makedirs("docs", exist_ok=True)
today = datetime.now(MEL).strftime("%Y-%m-%d")

for key, cfg in BAYS.items():
    extremes = fetch_extremes(cfg["lat"], cfg["lon"])
    top = build_top10(extremes)

    with open(cfg["out"], "w") as f:
        json.dump({
            "source": "WorldTides API",
            "timezone": "Australia/Melbourne",
            "generated_on": today,
            "top10": top,
        }, f, indent=2)
    print(f"{key}: wrote {len(top)} days from {len(extremes)} extremes -> {cfg['out']}")

    if cfg["tide_next"]:
        wp_node = build_tide_next(extremes)
        with open("docs/tide-next.json", "w") as f:
            json.dump({
                "timezone": "Australia/Melbourne",
                "generated_on": today,
                "wp": wp_node,
                "ppb": None,
                "source_wp": "WorldTides API",
                "source_ppb": None,
            }, f, indent=2)
        print(f"{key}: tide-next.json next high {wp_node['nextHighISO']} / next low {wp_node['nextLowISO']}")
