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

# ESPC-D-V02 is published on several hosts and the path has moved before, so
# try them in order rather than hard-coding one and calling it a day.
NCSS_BASES = [
    "https://ncss.hycom.org/thredds/ncss/ESPC-D-V02/uv3z",
    "https://tds.hycom.org/thredds/ncss/ESPC-D-V02/uv3z",
    "https://ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z",
    "https://tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z",
]


def fetch_series(lon, lat, t0, t1):
    """3-hourly HYCOM surface u,v at one point. Returns (times_h, u, v, source)."""
    q = {
        "var": ["water_u", "water_v"],
        "latitude": "%.4f" % lat,
        "longitude": "%.4f" % lon,
        "time_start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_end": t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vertCoord": "0",
        "accept": "csv",
    }
    qs = urllib.parse.urlencode(q, doseq=True)
    last = None
    for base in NCSS_BASES:
        url = "%s?%s" % (base, qs)
        try:
            with urllib.request.urlopen(url, timeout=180) as fh:
                raw = fh.read().decode("utf8", "replace")
        except Exception as exc:                            # noqa: BLE001
            last = "%s -> %s" % (base, exc)
            continue
        rows = [r for r in raw.splitlines() if r.strip()]
        if len(rows) < 10:
            last = "%s -> only %d rows" % (base, len(rows))
            continue
        head = [c.strip().strip('"') for c in rows[0].split(",")]

        def col(want):
            for i, c in enumerate(head):
                if c.split("[")[0].strip().lower() == want:
                    return i
            return None

        it, iu, iv = col("time"), col("water_u"), col("water_v")
        if None in (it, iu, iv):
            last = "%s -> columns %r" % (base, head)
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
            last = "%s -> only %d usable samples" % (base, len(ts))
            continue
        t_h = np.array([(x - ts[0]).total_seconds() / 3600.0 for x in ts])
        return t_h, np.array(us), np.array(vs), base
    raise RuntimeError("no HYCOM endpoint worked; last: %s" % last)


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

    results = []
    source = None
    for name, lon, lat, expect in POINTS:
        try:
            t_h, u, v, src = fetch_series(lon, lat, t0, t1)
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
