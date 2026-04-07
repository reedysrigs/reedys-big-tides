import requests
from datetime import datetime, timedelta
import json

API_KEY = "5fee6eb9-5c05-41f7-89d9-918e3961b35d"

LAT = -38.37
LON = 145.22

now = datetime.utcnow()
end = now + timedelta(days=60)

url = f"https://www.worldtides.info/api/v3?extremes&lat={LAT}&lon={LON}&start={int(now.timestamp())}&end={int(end.timestamp())}&key={API_KEY}"

res = requests.get(url)
data = res.json()

tides = []

for i in range(len(data["extremes"]) - 1):
    t1 = data["extremes"][i]
    t2 = data["extremes"][i + 1]

    if t1["type"] == "Low" and t2["type"] == "High":
        move = t2["height"] - t1["height"]

        tides.append({
            "date": datetime.fromtimestamp(t1["dt"]).strftime("%Y-%m-%d"),
            "moves": [{
                "low_time": datetime.fromtimestamp(t1["dt"]).strftime("%H%M"),
                "low_m": round(t1["height"], 2),
                "high_time": datetime.fromtimestamp(t2["dt"]).strftime("%H%M"),
                "high_m": round(t2["height"], 2),
                "move_m": round(move, 2)
            }],
            "max_move_m": round(move, 2)
        })

tides = sorted(tides, key=lambda x: x["max_move_m"], reverse=True)

top10 = tides[:10]

output = {
    "source": "WorldTides API",
    "timezone": "Australia/Melbourne",
    "generated_on": datetime.now().strftime("%Y-%m-%d"),
    "top10": top10
}

with open("docs/tides.json", "w") as f:
    json.dump(output, f, indent=2)
