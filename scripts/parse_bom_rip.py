#!/usr/bin/env python3
"""
Parse the Bureau's own tidal stream table for The Rip into docs/rip-streams.json.

Source: https://www.bom.gov.au/ntc/IDO59002/IDO59002_2026_VIC_TS001.pdf
These are the Bureau's published predictions, not a model of them.

WHY COORDINATES, NOT TEXT
-------------------------
Three months print side by side, two day-columns each, and an entry simply
vanishes where a day has fewer turns:

    1904 2210 3.88  1944 2241 3.47  2102 2358 3.88  2102  1927 2232 3.37 ...

That lone 2102 is a slack with no maximum after it. Read left to right there
is no way to know which of the six columns it belongs to. The x position says
so exactly. Column anchors are read off the header row at parse time rather
than hardcoded, so a change of layout between years is detected instead of
silently mis-parsed.

WHY THE DIRECTION IS VERIFIED, NOT ASSUMED
------------------------------------------
The table signs each rate but never states which sign is ingoing. Getting
that backwards would tell someone the Rip is running into the bay when it is
running out. So the sign is DERIVED: the Bureau states the ingoing stream
peaks at high water, so whichever sign lands nearest high water is ingoing.
If that correlation is not convincing, this refuses to publish.
"""
import io, json, os, re, sys
import datetime as dt
from collections import Counter

import requests

PDF = "https://www.bom.gov.au/ntc/IDO59002/IDO59002_2026_VIC_TS001.pdf"
OUT = "docs/rip-streams.json"
TZ = dt.timezone(dt.timedelta(hours=10))          # table is Local Standard Time
HEADS = (-38.2939, 144.6170)

MONTHS = {m: i + 1 for i, m in enumerate(
    "JANUARY FEBRUARY MARCH APRIL MAY JUNE JULY AUGUST "
    "SEPTEMBER OCTOBER NOVEMBER DECEMBER".split())}

TIME_RE = re.compile(r"^\d{4}$")
RATE_RE = re.compile(r"^-?\d+\.\d+$")


def centre(w):
    return (w["x0"] + w["x1"]) / 2.0


def column_anchors(words):
    """Read Slack/Max/Rate x-centres for all six day-columns off the header row."""
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"], 1), []).append(w)
    for top, ws in sorted(rows.items()):
        labels = [w["text"] for w in sorted(ws, key=centre)]
        if labels.count("Time") >= 6 and labels.count("Rate") >= 3:
            trip, cur = [], []
            for w in sorted(ws, key=centre):
                if w["text"] in ("Time", "Rate"):
                    cur.append(w)
                    if len(cur) == 3:
                        trip.append(tuple(centre(x) for x in cur))
                        cur = []
            if len(trip) == 6:
                return trip
    return None


def month_for_columns(words, anchors):
    """Map each of the six columns to a month, by x proximity to the month heading."""
    found = []
    for w in words:
        t = w["text"].upper().strip()
        if t in MONTHS:
            found.append((centre(w), MONTHS[t]))
    if len(found) < 1:
        return None
    found.sort()
    out = []
    for slack, _mx, _rx in anchors:
        best = min(found, key=lambda f: abs(f[0] - slack))
        out.append(best[1])
    return out


def parse_page(page, report):
    words = page.extract_words()
    if not words:
        return []
    anchors = column_anchors(words)
    if not anchors:
        return []
    months = month_for_columns(words, anchors)
    if not months:
        report.append("  page has columns but no month heading - skipped")
        return []

    day_x = [a[0] - 12 for a in anchors]      # day number sits left of the slack column

    rows = {}
    for w in words:
        rows.setdefault(round(w["top"], 1), []).append(w)

    events = []
    current_day = {}
    for top in sorted(rows):
        ws = sorted(rows[top], key=centre)
        texts = [w["text"] for w in ws]

        # a day-number row: short integers near the day-number x positions
        ints = [w for w in ws if w["text"].isdigit() and 1 <= int(w["text"]) <= 31
                and len(w["text"]) <= 2]
        if ints and len(ints) == len(texts):
            current_day = {}
            for w in ints:
                ci = min(range(6), key=lambda i: abs(centre(w) - day_x[i]))
                current_day[ci] = int(w["text"])
            continue
        if not current_day:
            continue

        # data row: assign every token to its nearest anchor
        slot = {}
        for w in ws:
            t = w["text"]
            if not (TIME_RE.match(t) or RATE_RE.match(t)):
                continue                       # weekday letters and stray marks
            cx = centre(w)
            best, bd = None, 1e9
            for ci, (sx, mx, rx) in enumerate(anchors):
                for fi, ax in enumerate((sx, mx, rx)):
                    d = abs(cx - ax)
                    if d < bd:
                        bd, best = d, (ci, fi)
            if bd > 14:                        # too far from any column to trust
                continue
            ci, fi = best
            if (RATE_RE.match(t) and fi != 2) or (TIME_RE.match(t) and fi == 2):
                continue                       # token type disagrees with its column
            slot.setdefault(ci, {})[fi] = t

        for ci, fields in slot.items():
            day = current_day.get(ci)
            if not day:
                continue
            mon = months[ci]
            def when(hhmm):
                try:
                    return dt.datetime(2026, mon, day, int(hhmm[:2]), int(hhmm[2:]), tzinfo=TZ)
                except ValueError:
                    return None
            if 0 in fields:
                t = when(fields[0])
                if t:
                    events.append({"at": t.isoformat(), "kind": "slack"})
            if 1 in fields and 2 in fields:
                t = when(fields[1])
                if t:
                    events.append({"at": t.isoformat(), "kind": "peak",
                                   "rate_kn": float(fields[2])})
    return events


def verify_direction(peaks, report):
    """Return 'neg' or 'pos' - which sign is ingoing - or None if unconvincing.

    BoM: the ingoing stream runs from about 3 hours before to about 3 hours
    after high water, so ingoing peaks AT high water.
    """
    key = os.environ.get("WORLD_TIDES_API_KEY", "").strip()
    if not key:
        report.append("  no WORLD_TIDES_API_KEY - cannot verify direction")
        return None
    start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    try:
        r = requests.get("https://www.worldtides.info/api/v3", timeout=40, params={
            "extremes": "", "lat": HEADS[0], "lon": HEADS[1],
            "start": int(start.timestamp()), "days": 7, "key": key})
        r.raise_for_status()
        ext = r.json().get("extremes", [])
    except Exception as e:
        report.append("  tide lookup failed: %s" % e)
        return None

    highs = [dt.datetime.fromtimestamp(e["dt"], dt.timezone.utc)
             for e in ext if str(e.get("type", "")).lower().startswith("h")]
    lows = [dt.datetime.fromtimestamp(e["dt"], dt.timezone.utc)
            for e in ext if str(e.get("type", "")).lower().startswith("l")]
    if len(highs) < 4 or len(lows) < 4:
        report.append("  not enough tide extremes to verify")
        return None

    lo_t = min(highs + lows)
    hi_t = max(highs + lows)
    near_high = Counter()
    used = 0
    for p in peaks:
        t = dt.datetime.fromisoformat(p["at"]).astimezone(dt.timezone.utc)
        if not (lo_t <= t <= hi_t):
            continue
        dh = min(abs((t - h).total_seconds()) for h in highs)
        dl = min(abs((t - l).total_seconds()) for l in lows)
        used += 1
        sign = "neg" if p["rate_kn"] < 0 else "pos"
        near_high[sign if dh < dl else ("pos" if sign == "neg" else "neg")] += 1

    if used < 8:
        report.append("  only %d peaks overlap the tide window - not enough" % used)
        return None
    total = sum(near_high.values())
    win, n = near_high.most_common(1)[0]
    frac = n / total
    report.append("  %d peaks checked against high water; '%s' is ingoing in %.0f%% of them"
                  % (used, win, 100 * frac))
    if frac < 0.8:
        report.append("  NOT CONVINCING - refusing to label direction")
        return None
    return win


def main():
    report = []
    try:
        r = requests.get(PDF, timeout=90, headers={"User-Agent": "reedysrigs-tides/1.0"})
        r.raise_for_status()
    except Exception as e:
        print("FAILED to fetch the table: %s" % e, file=sys.stderr)
        return 1

    import pdfplumber
    events = []
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            report.append("page %d" % pno)
            got = parse_page(page, report)
            report.append("  %d events" % len(got))
            events.extend(got)

    if len(events) < 2000:
        print("FAILED: only %d events parsed from a full year - layout has changed"
              % len(events), file=sys.stderr)
        print("\n".join(report), file=sys.stderr)
        return 1

    events.sort(key=lambda e: e["at"])
    peaks = [e for e in events if e["kind"] == "peak"]
    slacks = [e for e in events if e["kind"] == "slack"]

    report.append("")
    report.append("verifying which sign is ingoing")
    ingoing_sign = verify_direction(peaks, report)

    for e in peaks:
        if ingoing_sign is None:
            e["stream"] = None
        else:
            neg = e["rate_kn"] < 0
            e["stream"] = "ingoing" if (neg == (ingoing_sign == "neg")) else "outgoing"
        e["knots"] = round(abs(e["rate_kn"]), 2)

    now = dt.datetime.now(dt.timezone.utc)
    upcoming = [e for e in events if e["at"] >= now.isoformat()][:120]

    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Bureau of Meteorology tidal stream predictions, The Rip, "
                  "IDO59002_2026_VIC_TS001",
        "attribution": "This product is based on Bureau of Meteorology information "
                       "that has subsequently been modified. The Bureau does not "
                       "necessarily support or endorse, or have any connection with, "
                       "the product.",
        "not_for_navigation": True,
        "timezone": "Australia/Melbourne (table is Local Standard Time, UTC+10)",
        "lat": -38.2833, "lon": 144.6167,
        "direction_verified": ingoing_sign is not None,
        "events_total": len(events),
        "peaks_total": len(peaks),
        "slacks_total": len(slacks),
        "events": upcoming,
    }
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))

    print("\n".join(report))
    print("wrote %s: %d events (%d peaks, %d slacks), %d upcoming"
          % (OUT, len(events), len(peaks), len(slacks), len(upcoming)))
    if ingoing_sign is None:
        print("NOTE: direction could not be verified; stream left null", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
