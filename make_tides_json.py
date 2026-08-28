import os
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# --- Config -----------------------------------------------------------------
# Uses the repo secret WORLD_TIDES_API_KEY when it is set, otherwise falls
# back to the key below so the workflow runs either way with no setup.
API_KEY = os.environ.get("WORLD_TIDES_API_KEY", "").strip() or "5fee6eb9-5c05-41f7-89d9-918e3961b35d"

MEL = ZoneInfo("Australia/Melbourne")

BACK_DAYS = 8        # how far BACK to request, so the chart has real history
FETCH_DAYS = 33      # how far ahead to request (buffer beyond the 30-day window)
WINDOW_DAYS = 30     # only keep days within the next 30 days
TOP_N = 10           # biggest-movement days to output

# Chart datum offset for Western Port.
#
# WorldTides returns heights measured from MEAN SEA LEVEL, so low tide comes
# back negative. Published tide tables measure from the CHART DATUM, which is
# why every printed Western Port height is positive. Checked against Stony
# Point on 15 Aug 2026: the feed said +1.27 and -1.17 where the tables said
# 2.96 and 0.49 - a constant 1.67m apart.
#
# The page used to apply this offset itself, but only on the two-point
# fallback path. Applying it here means the heights are already in table
# terms by the time anything reads them, and every consumer agrees.
WP_DATUM = 1.67

# One entry per bay. PPB tide range is much smaller than Western Port - that's
# expected. If you want PPB referenced to a specific spot (the Heads, Williamstown,
# Geelong etc.), just change this lat/lon and re-run; WorldTides snaps to the
# nearest tide station.
#
# NOTE: the wp lat/lon below is STONY POINT. Every Western Port ramp on the
# fishing window currently reads this one station. Hastings, Rhyll, Corinella
# and the rest all have their own timing and range, so if a ramp looks wrong
# against a published table this is the first thing to check.
BAYS = {
    "wp":  {"lat": -38.37, "lon": 145.22, "out": "docs/tides.json",     "tide_next": True,  "datum": WP_DATUM},
    # Frankston pier. This was -38.00, 144.85 - open water mid-bay, which
    # WorldTides snapped to a big-range station and gave Port Phillip a 1.34m
    # swing. Frankston's published table on 28 Aug 2026 runs 0.26 to 0.76,
    # about half a metre, which is what the inside of the bay actually does.
    #
    # Datum 0.54: WorldTides measures from mean sea level, the tables from
    # chart datum. Frankston's published tides sit between 0.26 and 0.82, so
    # mid-water is about 0.54 above the datum. CHECK THIS after the first run
    # - compare a low against Willy Weather's Frankston page and shift this
    # number by whatever the gap is.
    "ppb": {"lat": -38.14, "lon": 145.12, "out": "docs/tides-ppb.json", "tide_next": False, "datum": 0.54},
}

now_utc = datetime.now(timezone.utc)
# Start the fetch BEFORE now. The chart draws up to 7 days of history, and
# the page only ever had points from the first real extreme forward - so
# everything left of the NOW pole flattened into a straight line. Asking for
# a week back fills it with the real thing.
start = int((now_utc - timedelta(days=BACK_DAYS)).timestamp())
length = (BACK_DAYS + FETCH_DAYS) * 86400   # WorldTides uses 'length' in SECONDS, NOT 'end'
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


def build_top10(extremes, datum=0.0):
    """Biggest Low<->High swing per day, top N days by size, within the window.

    low_m and high_m are datum-shifted, because the Big Tides tab prints them
    straight to the screen. Un-shifted they came out MSL-referenced and every
    low displayed NEGATIVE - the 15 Sep spring showed as -1.35 / 1.32 where
    the published Stony Point table says 0.32 / 2.99, and it contradicted the
    tide chart on the same page. move_m and max_move_m are differences, so the
    offset cancels and they were always right.
    """
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
        # the fetch now reaches back a week for the chart's history - big-tide
        # days are a look-ahead list, so drop anything already gone
        if earlier < today_start:
            continue
        move = round(high["height"] - low["height"], 2)
        date_str = earlier.strftime("%Y-%m-%d")
        swing = {
            "date": date_str,
            "moves": [{
                "low_time":  low_dt.strftime("%H%M"),
                "low_m":     round(low["height"] + datum, 2),
                "high_time": high_dt.strftime("%H%M"),
                "high_m":    round(high["height"] + datum, 2),
                "move_m":    move,
            }],
            "max_move_m": move,
        }
        if date_str not in day_best or move > day_best[date_str]["max_move_m"]:
            day_best[date_str] = swing
    return sorted(day_best.values(), key=lambda x: x["max_move_m"], reverse=True)[:TOP_N]


def build_extremes_list(extremes, datum, days=14, back_days=BACK_DAYS):
    """Every high and low across the next `days`, in the shape the fishing
    window's buildTideCurve() already reads: date / height / type.

    This is the whole point of the rewrite. The API hands back 33 days of real
    extremes and the old script kept exactly two of them - the next high and
    the next low - so the page had to invent every other tide for the next
    twelve days off a generic spring-neap formula. That is why every high
    printed 2.4m and every low 1.3m: same amplitude, over and over, when the
    real tide builds and eases through the cycle.

    Heights are shifted to the chart datum here so they come out in the same
    terms as a published tide table.
    """
    end = (now_utc + timedelta(days=days)).astimezone(MEL)
    begin = (now_utc - timedelta(days=back_days)).astimezone(MEL)
    out = []
    for e in extremes:
        dt = datetime.fromtimestamp(e["dt"], MEL)
        if dt < begin:
            continue
        if dt > end:
            break
        out.append({
            "date":   dt.isoformat(),
            "height": round(e["height"] + datum, 2),
            "type":   e["type"],
        })
    return out


def build_tide_next(extremes, datum):
    """Next high / next low / range. Kept for anything still reading it."""
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
        # raw, MSL-referenced - the page adds its own offset on this path
        "nextHigh_m":  round(next_high["height"], 2) if next_high else None,
        "nextLow_m":   round(next_low["height"], 2) if next_low else None,
        "range_m":     range_m,
    }


os.makedirs("docs", exist_ok=True)
now_mel = datetime.now(MEL)
today = now_mel.strftime("%Y-%m-%d")
today_start = now_mel.replace(hour=0, minute=0, second=0, microsecond=0)

for key, cfg in BAYS.items():
    extremes = fetch_extremes(cfg["lat"], cfg["lon"])
    top = build_top10(extremes, cfg["datum"])

    with open(cfg["out"], "w") as f:
        json.dump({
            "source": "WorldTides API",
            "timezone": "Australia/Melbourne",
            "generated_on": today,
            "top10": top,
        }, f, indent=2)
    print(f"{key}: wrote {len(top)} days from {len(extremes)} extremes -> {cfg['out']}")

    if cfg["tide_next"]:
        wp_node = build_tide_next(extremes, cfg["datum"])
        ex_list = build_extremes_list(extremes, cfg["datum"])
        with open("docs/tide-next.json", "w") as f:
            json.dump({
                "timezone": "Australia/Melbourne",
                "generated_on": today,
                # full ISO stamp, so a stale file is obvious at a glance
                # rather than only showing the date it was built
                "generated_at": now_mel.isoformat(),
                "station": "Western Port (Stony Point)",
                "datum_offset_m": cfg["datum"],
                # THE important field - real highs and lows for the next 14
                # days, already datum-shifted. buildTideCurve() picks this up
                # and stops extrapolating.
                "extremes": ex_list,
                "wp": wp_node,
                "ppb": None,
                "source_wp": "WorldTides API",
                "source_ppb": None,
            }, f, indent=2)
        print(f"{key}: tide-next.json {len(ex_list)} extremes, "
              f"first {ex_list[0]['date'] if ex_list else 'none'}")
