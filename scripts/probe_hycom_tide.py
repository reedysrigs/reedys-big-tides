#!/usr/bin/env python3
"""
Does HYCOM already contain the tide?

This decides whether the FES2014 field can be ADDED to the existing HYCOM
current field or not.  If HYCOM already carries tidal motion, adding FES on top
double-counts it everywhere shallow - which would be worse than shipping
neither, because the error would be largest exactly where the tide matters.

The question is answered by measurement, not by reading documentation:

  1. Pull a two-week time series of HYCOM water_u/water_v at a few points.
     ESPC-D-V02 is 3-hourly, so the Nyquist period is 6 h and the principal
     semidiurnal M2 (12.4206 h) is comfortably resolvable.
  2. Least-squares fit mean + trend + M2 + S2 + K1 + O1 to that series.
  3. Read the M2 amplitude FES2014 gives at the same point, from the cached
     constituent files.
  4. Compare.  If HYCOM's fitted M2 is a few mm/s it has no tide and the two
     fields add.  If it is the same order as FES's M2, HYCOM already has the
     tide and they must not be added.

Points are chosen so the answer is unambiguous: Banks Strait and mid Bass
Strait are strongly tidal; the deep Tasman point is a control where tidal
current is weak, so a model WITH tide and a model WITHOUT tide look similar
there.  Agreement at the control plus disagreement at the tidal points is the
signature we are looking for.

Writes a plain-language verdict to docs/_hycom_tide_probe.md.  Exits non-zero
only if it could not get the data at all - an inconclusive result is still a
result and must not look like a passing test.
"""
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

# period in hours
CONSTITUENT_PERIODS = {
    "M2": 12.420601,
    "S2": 12.000000,
    "N2": 12.658348,
    "K1": 23.934470,
    "O1": 25.819342,
}

POINTS = [
    # name,                    lon,     lat,   expectation
    ("Banks Strait",          148.10, -40.70, "strongly tidal"),
    ("Mid Bass Strait",       145.50, -39.50, "tidal"),
    ("Shelf off Portland",    141.50, -39.20, "tidal"),
    ("Deep Tasman (control)", 152.50, -36.00, "weakly tidal"),
]

DAYS = 14
OUT_MD = "docs/_hycom_tide_probe.md"

# ESPC-D-V02 is published on several hosts and the path has moved more than
# once, so try a spread rather than hard-coding one and calling it a day.
#
# THREDDS 5 split the subset service into /ncss/grid/ and /ncss/point/; older
# builds serve it at plain /ncss/. A request to the wrong one answers HTTP 400,
# which is exactly what the first run of this probe got on every candidate - a
# 400 means the server is THERE and rejected the query, so the fix is the URL
# or the parameters, not the network.
_HOSTS = ["https://ncss.hycom.org", "https://tds.hycom.org"]
_PATHS = [
    "/thredds/ncss/grid/ESPC-D-V02/uv3z",
    "/thredds/ncss/ESPC-D-V02/uv3z",
    "/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z",
    "/thredds/ncss/GLBy0.08/expt_93.0/uv3z",
    "/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z",
]
NCSS_BASES = [h + p for p in _PATHS for h in _HOSTS]


def http_get(url, timeout=120):
    """Returns (status, body_text, error_text). Never raises."""
    req = urllib.request.Request(url, headers={"User-Agent": "reedys-rigs-probe/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return fh.getcode(), fh.read().decode("utf8", "replace"), None
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf8", "replace")[:400]
        except Exception:                                   # noqa: BLE001
            pass
        return exc.code, body, "HTTP %s" % exc.code
    except Exception as exc:                                # noqa: BLE001
        return None, "", str(exc)[:200]


def _parse_iso(s):
    s = s.strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s[:len(fmt) + 2].rstrip("T:"), fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s[:19])
    except ValueError:
        return None


def catalog_datasets(log):
    """Enumerate real uv3z grid datasets from the THREDDS catalogs.

    The ESPC-D-V02 paths answer 200 with an EMPTY body, which means the path
    resolves but is not itself a grid dataset - typically a catalog whose
    members are split by year. So ask the catalogs what exists instead of
    guessing URLs.
    """
    cats = []
    for host in _HOSTS:
        for p in ("ESPC-D-V02/uv3z", "ESPC-D-V02", "GLBy0.08/expt_93.0",
                  "FMRC_ESPC-D-V02_uv3z"):
            cats.append("%s/thredds/catalog/%s/catalog.xml" % (host, p))
    found = []
    seen = set()
    log("### Catalog walk")
    log("")
    log("| catalog | status | urlPaths found |")
    log("|---|---|---|")
    for c in cats:
        status, body, err = http_get(c, timeout=60)
        paths = []
        if status == 200:
            paths = re.findall(r'urlPath="([^"]+)"', body)
            # also pick up nested catalogRefs one level down
            for ref in re.findall(r'xlink:href="([^"]+\.xml)"', body)[:12]:
                sub = urllib.parse.urljoin(c, ref)
                s2, b2, _ = http_get(sub, timeout=45)
                if s2 == 200:
                    paths += re.findall(r'urlPath="([^"]+)"', b2)
        hits = [p for p in dict.fromkeys(paths) if "uv3z" in p.lower()]
        log("| `%s` | %s | %d |" % (c.replace("https://", ""),
                                    status if status else (err or "-")[:20], len(hits)))
        host = "https://" + urllib.parse.urlparse(c).netloc
        for p in hits:
            for pref in ("/thredds/ncss/grid/", "/thredds/ncss/"):
                u = host + pref + p
                if u not in seen:
                    seen.add(u)
                    found.append(u)
    log("")
    return found


def describe(base):
    """(ok, variables, t_start, t_end) from an NCSS grid dataset description."""
    status, body, _ = http_get(base + "/dataset.xml", timeout=60)
    if status != 200 or not body.strip():
        return False, [], None, None
    if not any(k in body for k in ("gridDataset", "GridDataset", "gridSet",
                                   "capabilities")):
        return False, [], None, None
    names = sorted(set(re.findall(r'name="(water_[a-z_]+)"', body)))
    t0 = t1 = None
    m = re.search(r"<TimeSpan>(.*?)</TimeSpan>", body, re.S)
    span = m.group(1) if m else body
    s = re.search(r"<start>([^<]+)</start>", span)
    e = re.search(r"<end>([^<]+)</end>", span)
    if s:
        t0 = _parse_iso(s.group(1))
    if e:
        t1 = _parse_iso(e.group(1))
    return True, names, t0, t1


def discover(log):
    """Find usable endpoints and, for each, the time window we may ask for.

    Returns a list of (base, t_start, t_end), best first: prefers ESPC-D-V02
    (the product the offshore page actually uses) and the most recent coverage.
    """
    candidates = catalog_datasets(log) + NCSS_BASES
    rows = []
    log("### Endpoint descriptions")
    log("")
    log("| endpoint | usable | water vars | coverage |")
    log("|---|---|---|---|")
    for base in dict.fromkeys(candidates):
        ok, names, t0, t1 = describe(base)
        have_uv = "water_u" in names and "water_v" in names
        log("| `%s` | %s | %s | %s |" % (
            base.replace("https://", ""),
            "yes" if (ok and have_uv) else "no",
            len([n for n in names if not n.endswith("_bottom")]) or "-",
            ("%s .. %s" % (t0.strftime("%Y-%m-%d") if t0 else "?",
                           t1.strftime("%Y-%m-%d") if t1 else "?"))
            if (t0 or t1) else "not advertised"))
        if ok and have_uv and t0 and t1 and (t1 - t0) > dt.timedelta(days=DAYS + 1):
            rows.append((base, t0, t1))
    log("")
    # Prefer the product the page uses, then the most recent coverage.
    rows.sort(key=lambda r: (0 if "espc" in r[0].lower() else 1, -r[2].timestamp()))
    if rows:
        b, t0, t1 = rows[0]
        log("Chosen: `%s`" % b)
        log("")
        log("- coverage %s .. %s" % (t0.strftime("%Y-%m-%dT%H:%MZ"),
                                     t1.strftime("%Y-%m-%dT%H:%MZ")))
        log("- NOTE: whether a model contains the tide is a property of the model,")
        log("  so any window it covers answers the question. We take the last")
        log("  %d days of its coverage rather than insisting on today." % DAYS)
        if "espc" not in b.lower():
            log("- WARNING: this is NOT ESPC-D-V02, which is what the offshore page")
            log("  uses. It is the same HYCOM+NCODA lineage, so the answer is")
            log("  strongly indicative, but it is not the identical product and")
            log("  this report must not be read as if it were.")
        log("")
    else:
        log("No endpoint advertised both water_u/water_v and enough coverage.")
        log("")
    return rows


def query_variants(lon, lat, t0, t1):
    """Several plausible NCSS point-query spellings, most likely first."""
    common = {
        "var": ["water_u", "water_v"],
        "latitude": "%.4f" % lat,
        "longitude": "%.4f" % lon,
        "time_start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_end": t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = []
    for extra in (
        {"vertCoord": "0", "accept": "csv"},
        {"accept": "csv"},                      # let it pick the top level
        {"vertCoord": "0.0", "accept": "csv"},
        {"vertCoord": "0", "accept": "text/csv"},
        {"vertCoord": "0", "accept": "csv", "horizStride": "1"},
    ):
        q = dict(common)
        q.update(extra)
        out.append(urllib.parse.urlencode(q, doseq=True))
    return out


def fetch_series(lon, lat, t0, t1, bases, log=None):
    """3-hourly HYCOM surface u,v at one point. Returns (times_h, u, v, source).

    Tries every (base, query-spelling) pair and records what each one said, so a
    failure produces a diagnosis instead of just "it did not work".
    """
    tried = []
    for base in bases:
        for qs in query_variants(lon, lat, t0, t1):
            url = "%s?%s" % (base, qs)
            status, raw, err = http_get(url, timeout=180)
            if err or status != 200:
                tried.append("%s [%s] -> %s %s" % (
                    base.replace("https://", ""), qs[:46], status or "-",
                    (raw[:120].replace("\n", " ") if raw else (err or ""))))
                continue
            rows = [r for r in raw.splitlines() if r.strip()]
            if len(rows) < 10:
                tried.append("%s [%s] -> 200 but only %d rows" % (
                    base.replace("https://", ""), qs[:46], len(rows)))
                continue
            head = [c.strip().strip('"') for c in rows[0].split(",")]

            def col(want, _head=head):
                for i, c in enumerate(_head):
                    if c.split("[")[0].strip().lower() == want:
                        return i
                return None

            it, iu, iv = col("time"), col("water_u"), col("water_v")
            if None in (it, iu, iv):
                tried.append("%s [%s] -> 200, unexpected columns %r" % (
                    base.replace("https://", ""), qs[:46], head[:8]))
                continue
            ts, us, vs = [], [], []
            for r in rows[1:]:
                p = [c.strip().strip('"') for c in r.split(",")]
                if len(p) <= max(it, iu, iv):
                    continue
                try:
                    when = dt.datetime.strptime(p[it][:19], "%Y-%m-%dT%H:%M:%S")
                    uu, vv = float(p[iu]), float(p[iv])
                except ValueError:
                    continue
                if not (np.isfinite(uu) and np.isfinite(vv)):
                    continue
                ts.append(when)
                us.append(uu)
                vs.append(vv)
            if len(ts) < 20:
                tried.append("%s [%s] -> 200 but only %d usable samples" % (
                    base.replace("https://", ""), qs[:46], len(ts)))
                continue
            t_h = np.array([(x - ts[0]).total_seconds() / 3600.0 for x in ts])
            if log:
                log("Working query: `%s?%s`" % (base, qs))
                log("")
            return t_h, np.array(us), np.array(vs), base
    raise RuntimeError("no HYCOM endpoint and query combination worked.\n"
                       + "\n".join("  " + t for t in tried))


def harmonic_fit(t_h, series, periods):
    """Least-squares mean + linear trend + cos/sin per period.

    Returns {name: amplitude}. Amplitude is sqrt(a^2+b^2) for that pair, in the
    units of `series`.
    """
    cols = [np.ones_like(t_h), t_h]
    names = []
    for n, p in periods.items():
        w = 2 * np.pi / p
        cols += [np.cos(w * t_h), np.sin(w * t_h)]
        names.append(n)
    A = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(A, series, rcond=None)
    out = {}
    for i, n in enumerate(names):
        a, b = coef[2 + 2 * i], coef[3 + 2 * i]
        out[n] = float(np.hypot(a, b))
    resid = series - A @ coef
    return out, float(np.std(resid))


def fes_m2_amplitude(lon, lat, fes_dir):
    """FES2014 M2 current amplitude at a point, cm/s -> m/s. (u_amp, v_amp)."""
    import xarray as xr

    got = []
    for sub, amp_var in (("eastward_velocity", "Ua"), ("northward_velocity", "Va")):
        path = os.path.join(fes_dir, "fes2014", sub, "m2.nc")
        if not os.path.exists(path):
            return None
        ds = xr.open_dataset(path, engine="netcdf4")
        try:
            latn = "lat" if "lat" in ds.coords else "latitude"
            lonn = "lon" if "lon" in ds.coords else "longitude"
            lo = lon % 360 if float(ds[lonn].max()) > 180 else lon
            v = ds[amp_var].sel({latn: lat, lonn: lo}, method="nearest")
            val = float(v.values)
        finally:
            ds.close()
        got.append(np.nan if not np.isfinite(val) or val == 0 else val / 100.0)
    return tuple(got)


def main():
    fes_dir = os.environ.get("FES_DIR", "fes-data")
    t1 = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    t0 = t1 - dt.timedelta(days=DAYS)

    lines = []
    w = lines.append
    w("# Does HYCOM already contain the tide?")
    w("")
    w("Generated %s" % t1.strftime("%Y-%m-%dT%H:%M:%SZ"))
    w("")
    w("Method: least-squares harmonic fit of mean + trend + M2/S2/N2/K1/O1 to a")
    w("%d-day HYCOM time series, against the M2 amplitude FES2014 gives at the" % DAYS)
    w("same point. If HYCOM has no tide its fitted M2 is near zero and the two")
    w("fields can be added. If its M2 is the same order as FES's, they cannot.")
    w("")

    rows = discover(w)
    if rows:
        # Use the end of the chosen dataset's own coverage, not "now".
        bases = [r[0] for r in rows]
        cov_end = rows[0][2]
        t1 = min(t1, cov_end)
        t0 = t1 - dt.timedelta(days=DAYS)
        if t0 < rows[0][1]:
            t0 = rows[0][1]
        w("Window actually requested: %s .. %s" % (
            t0.strftime("%Y-%m-%dT%H:%MZ"), t1.strftime("%Y-%m-%dT%H:%MZ")))
        w("")
    else:
        w("Falling back to trying every candidate with today's window - the")
        w("descriptions may be disabled while the subset service still works.")
        w("")
        bases = NCSS_BASES

    results = []
    source = None
    for name, lon, lat, expect in POINTS:
        try:
            t_h, u, v, src = fetch_series(lon, lat, t0, t1, bases,
                                          log=(w if source is None else None))
            source = source or src
        except Exception as exc:                            # noqa: BLE001
            w("## %s - COULD NOT FETCH" % name)
            w("")
            w("```")
            w(str(exc))
            w("```")
            w("")
            results.append((name, None))
            continue

        au, ru = harmonic_fit(t_h, u, CONSTITUENT_PERIODS)
        av, rv = harmonic_fit(t_h, v, CONSTITUENT_PERIODS)
        fes = fes_m2_amplitude(lon, lat, fes_dir)

        hy_m2 = float(np.hypot(au["M2"], av["M2"]))
        fe_m2 = (float(np.hypot(*[x for x in fes]))
                 if fes and all(np.isfinite(fes)) else float("nan"))
        ratio = hy_m2 / fe_m2 if fe_m2 and np.isfinite(fe_m2) and fe_m2 > 0 else float("nan")

        w("## %s  (%.2fE %.2fS, %s)" % (name, lon, abs(lat), expect))
        w("")
        w("%d samples over %.1f days, HYCOM residual scatter %.3f / %.3f m/s (u/v)"
          % (len(t_h), t_h[-1] / 24.0, ru, rv))
        w("")
        w("| constituent | HYCOM u amp | HYCOM v amp |")
        w("|---|---|---|")
        for c in CONSTITUENT_PERIODS:
            w("| %s | %.4f m/s | %.4f m/s |" % (c, au[c], av[c]))
        w("")
        w("- HYCOM M2 speed amplitude: **%.4f m/s**" % hy_m2)
        if np.isfinite(fe_m2):
            w("- FES2014 M2 speed amplitude at the same point: **%.4f m/s**" % fe_m2)
            w("- ratio HYCOM/FES: **%.2f**" % ratio)
        else:
            w("- FES2014 M2 at this point: not available (land cell or files absent)")
        w("")
        results.append((name, (hy_m2, fe_m2, ratio)))

    good = [r for _, r in results if r and np.isfinite(r[2])]
    w("## Verdict")
    w("")
    if not good:
        w("**INCONCLUSIVE** - no point produced both a HYCOM fit and an FES value.")
        w("Do not change the page on the strength of this run.")
        verdict = "inconclusive"
    else:
        ratios = np.array([r[2] for r in good])
        med = float(np.median(ratios))
        w("Median HYCOM/FES M2 ratio across %d points: **%.2f**" % (len(good), med))
        w("")
        if med < 0.15:
            w("**HYCOM DOES NOT CONTAIN THE TIDE.** Its M2 is a small fraction of")
            w("FES's, consistent with no tidal forcing. The FES field can be ADDED")
            w("to HYCOM: total = HYCOM (ocean circulation) + FES (tide).")
            verdict = "no tide in HYCOM - add the fields"
        elif med > 0.5:
            w("**HYCOM ALREADY CONTAINS THE TIDE.** Its M2 is the same order as")
            w("FES's. The fields MUST NOT be added - doing so would double-count")
            w("the tide everywhere shallow. Either keep using HYCOM alone, or")
            w("replace it with FES in shallow water rather than summing.")
            verdict = "tide present in HYCOM - do NOT add"
        else:
            w("**AMBIGUOUS** (ratio %.2f, between 0.15 and 0.5). Partial tidal" % med)
            w("signal, or the fit is contaminated by genuine non-tidal variability")
            w("at these points. Do not add the fields on this evidence; widen the")
            w("probe before deciding.")
            verdict = "ambiguous - do not add yet"
    w("")
    if source:
        w("HYCOM source: `%s`" % source)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    print("\nverdict: %s" % verdict)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
