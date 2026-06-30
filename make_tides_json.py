import os
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# --- Config -----------------------------------------------------------------
API_KEY = "5fee6eb9-5c05-41f7-89d9-918e3961b35d"
LAT = -38.37
LON = 145.22
MEL = ZoneInfo("Australia/Melbourne")

FETCH_DAYS = 33      # how far ahead to request (buffer beyond the 30-day window)
WINDOW_DAYS = 30     # only keep days within the next 30 days
TOP_N = 10           # biggest-movement days to output

# --- Request ----------------------------------------------------------------
now_utc = datetime.now(timezone.utc)
start = int(now_utc.timestamp())
length = FETCH_DAYS * 86400          # WorldTides uses 'length' in SECONDS, NOT 'end'

url = (
    "https://www.worldtides.info/api/v3"
    f"?extremes&lat={LAT}&lon={LON}"
    f"&start={start}&length={length}"
    f"&key={API_KEY}"
)

res = requests.get(url, timeout=30)
res.raise_for_status()
data = res.json()
extremes = data.get("extremes", [])

# --- Build a swing for every consecutive Low<->High pair --------------------
cutoff = now_utc + timedelta(days=WINDOW_DAYS)
day_best = {}   # "YYYY-MM-DD" -> best swing for that day

for i in range(len(extremes) - 1):
    a = extremes[i]
    b = extremes[i + 1]

    # one must be Low and the other High (catches both Low->High and High->Low)
    if {a["type"], b["type"]} != {"Low", "High"}:
        continue

    low  = a if a["type"] == "Low"  else b
    high = a if a["type"] == "High" else b

    # WorldTides 'dt' is a UTC unix timestamp -> convert to Melbourne local time
    low_dt  = datetime.fromtimestamp(low["dt"],  MEL)
    high_dt = datetime.fromtimestamp(high["dt"], MEL)
    earlier = min(low_dt, high_dt)

    # only keep swings that start within the next WINDOW_DAYS
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

    # keep only the biggest swing per day
    if date_str not in day_best or move > day_best[date_str]["max_move_m"]:
        day_best[date_str] = swing

# --- Top N days by movement size --------------------------------------------
top = sorted(day_best.values(), key=lambda x: x["max_move_m"], reverse=True)[:TOP_N]

output = {
    "source": "WorldTides API",
    "timezone": "Australia/Melbourne",
    "generated_on": datetime.now(MEL).strftime("%Y-%m-%d"),
    "top10": top,
}

os.makedirs("docs", exist_ok=True)
with open("docs/tides.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Wrote {len(top)} days from {len(extremes)} extremes.")
