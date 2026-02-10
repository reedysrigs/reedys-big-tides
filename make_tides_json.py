import os, re, json
from datetime import date, timedelta
import requests
import pdfplumber

MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
}

def download(url: str, out_path: str):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)

def parse_bom_pdf(pdf_path: str, year: int):
    data = {}
    current_month = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            for ln in lines:
                if ln in MONTHS:
                    current_month = MONTHS[ln]
                    continue
                if current_month is None:
                    continue

                m = re.match(r"^(\d{1,2})\b", ln)
                if not m:
                    continue

                day = int(m.group(1))
                pairs = re.findall(r"(\d{3,4})\s+(\d\.\d{2})", ln)
                if not pairs:
                    continue

                try:
                    d = date(year, current_month, day)
                except ValueError:
                    continue

                events = []
                for t, h in pairs:
                    t = t.zfill(4)
                    events.append((t, float(h)))

                data.setdefault(d, []).extend(events)

    for d in data:
        data[d].sort(key=lambda x: x[0])
    return data

def build_low_to_high_pairs(events):
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
                "move_m": round(h2 - h1, 2)
            })
    return pairs

def main():
    bom_pdf_url = os.environ.get("BOM_PDF_URL", "").strip()
    if not bom_pdf_url:
        raise SystemExit("Missing BOM_PDF_URL. Set it as a GitHub repo variable.")

    days_ahead = int(os.environ.get("DAYS_AHEAD", "60"))
    high_thr = float(os.environ.get("HIGH_THRESHOLD", "2.8"))
    move_thr = float(os.environ.get("MOVE_THRESHOLD", "2.2"))
    tz_label = os.environ.get("TZ_LABEL", "Australia/Melbourne")

    today = date.today()
    end = today + timedelta(days=days_ahead)
    year = today.year

    os.makedirs("tmp", exist_ok=True)
    pdf_path = "tmp/bom_tides.pdf"
    download(bom_pdf_url, pdf_path)

    data = parse_bom_pdf(pdf_path, year)

    out = {
        "source": "Bureau of Meteorology (BoM) tide tables – Western Port (Stony Point)",
        "source_pdf": bom_pdf_url,
        "timezone": tz_label,
        "generated_on": today.isoformat(),
        "days_ahead": days_ahead,
        "thresholds": {"high_m": high_thr, "move_m": move_thr},
        "days": []
    }

    d = today
    while d <= end:
        events = data.get(d)
        if events:
            pairs = build_low_to_high_pairs(events)
            if pairs:
                max_high = max(p["high_m"] for p in pairs)
                max_move = max(p["move_m"] for p in pairs)
                if (max_high >= high_thr) or (max_move >= move_thr):
                    out["days"].append({
                        "date": d.isoformat(),
                        "pairs": pairs,
                        "max_high_m": round(max_high, 2),
                        "max_move_m": round(max_move, 2)
                    })
        d += timedelta(days=1)

    os.makedirs("docs", exist_ok=True)
    with open("docs/tides.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote docs/tides.json with {len(out['days'])} big-tide day(s).")

if __name__ == "__main__":
    main()
