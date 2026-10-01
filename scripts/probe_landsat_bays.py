#!/usr/bin/env python3
"""
Can we get 100 m thermal imagery over Port Phillip Bay and Western Port?

The existing SST is ~2 km. Port Phillip is about 50 km across, so the bay is
roughly 25 pixels wide and every structure inside it - channel edges, the warm
shallow margins over the banks, the cold plume through the Rip - is averaged
away before it can be drawn. Landsat's thermal band is 100 m, which is about
400x more detail by area.

This probe answers, in ONE run, every unknown that would otherwise cost a
workflow each. It is deliberately verbose and commits its findings, because the
Actions log cannot be downloaded from the sandbox that wrote this.

Questions:
  1. Is a STAC catalog reachable from Actions at all, and which one?
  2. Which Landsat scenes actually cover the two bays, how recent, how cloudy?
  3. Does anonymous asset signing work (Planetary Computer needs a SAS token)?
  4. Can a WINDOW of the ST_B10 band be read over HTTPS without pulling the
     whole ~1 GB scene? If not, this is not viable on a free runner.
  5. What do the numbers look like over water once scaled to degrees C?

Exits non-zero if it could not answer 1-4, so an unusable result cannot be
mistaken for a working feed.
"""
import datetime as dt
import json
import os
import sys
import traceback

# Port Phillip Bay + Western Port, with a margin for the approaches.
BBOX = [144.35, -38.70, 145.60, -37.80]          # W, S, E, N
DAYS_BACK = 180
OUT_MD = "docs/_landsat_bays_probe.md"

# Collection 2 Level-2 surface temperature scaling, from the USGS product
# guide: Kelvin = DN * 0.00341802 + 149.0
ST_SCALE, ST_OFFSET = 0.00341802, 149.0

CATALOGS = [
    ("Planetary Computer", "https://planetarycomputer.microsoft.com/api/stac/v1",
     ["landsat-c2-l2"]),
    ("Earth Search (AWS)", "https://earth-search.aws.element84.com/v1",
     ["landsat-c2-l2", "landsat-c2l2-sr"]),
]

lines = []


def w(s=""):
    lines.append(s)
    print(s, flush=True)


def flush(ok):
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def main():
    w("# Landsat thermal over Port Phillip Bay and Western Port")
    w("")
    w("Generated %s" % dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    w("")
    w("Box searched: %.2f..%.2f E, %.2f..%.2f S, last %d days"
      % (BBOX[0], BBOX[2], abs(BBOX[3]), abs(BBOX[1]), DAYS_BACK))
    w("")

    try:
        from pystac_client import Client
    except Exception as exc:                                # noqa: BLE001
        w("**FAILED**: pystac_client did not import: %s" % exc)
        return flush(False)

    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=DAYS_BACK)
    window = "%s/%s" % (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    items, used_cat, used_coll = None, None, None
    w("## 1. Catalog reachability")
    w("")
    w("| catalog | collection | result |")
    w("|---|---|---|")
    for name, url, colls in CATALOGS:
        for coll in colls:
            try:
                cat = Client.open(url)
                search = cat.search(collections=[coll], bbox=BBOX,
                                    datetime=window, limit=100)
                got = list(search.items())
                w("| %s | `%s` | %d scenes |" % (name, coll, len(got)))
                if got and items is None:
                    items, used_cat, used_coll = got, (name, url), coll
            except Exception as exc:                        # noqa: BLE001
                w("| %s | `%s` | %s |"
                  % (name, coll, str(exc)[:110].replace("|", "/")))
    w("")
    if not items:
        w("**FAILED**: no catalog returned any scene. Nothing else can be tested.")
        return flush(False)
    w("Using **%s** / `%s`" % (used_cat[0], used_coll))
    w("")

    # ---------------------------------------------------------------- 2
    w("## 2. Scenes over the bays")
    w("")
    rows = []
    for it in items:
        p = it.properties
        rows.append({
            "id": it.id,
            "date": (p.get("datetime") or "")[:19],
            "cloud": p.get("eo:cloud_cover"),
            "platform": p.get("platform") or p.get("constellation"),
            "wrs": "%s/%s" % (p.get("landsat:wrs_path"), p.get("landsat:wrs_row")),
            "assets": sorted(it.assets.keys()),
            "item": it,
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    w("%d scenes in the window. Ten most recent:" % len(rows))
    w("")
    w("| date | platform | path/row | cloud % | has thermal |")
    w("|---|---|---|---|---|")
    for r in rows[:10]:
        thermal = [a for a in r["assets"] if a.lower() in
                   ("lwir11", "lwir", "st_b10", "surface_temperature", "st")]
        w("| %s | %s | %s | %s | %s |"
          % (r["date"], r["platform"], r["wrs"],
             ("%.1f" % r["cloud"]) if r["cloud"] is not None else "?",
             ", ".join("`%s`" % t for t in thermal) or "NONE"))
    w("")
    clear = [r for r in rows if (r["cloud"] is not None and r["cloud"] < 25)]
    w("Scenes under 25%% cloud: **%d of %d**" % (len(clear), len(rows)))
    if len(rows) > 1:
        ds = sorted({r["date"][:10] for r in rows})
        gaps = []
        for a, b in zip(ds, ds[1:]):
            da = dt.datetime.strptime(a, "%Y-%m-%d")
            db = dt.datetime.strptime(b, "%Y-%m-%d")
            gaps.append((db - da).days)
        if gaps:
            w("Distinct pass dates: %d. Median gap between passes: **%d days**"
              % (len(ds), sorted(gaps)[len(gaps) // 2]))
    w("")
    w("Asset names on the newest scene:")
    w("")
    w("```")
    w(", ".join(rows[0]["assets"]))
    w("```")
    w("")

    # ---------------------------------------------------------------- 3 & 4
    w("## 3-4. Signing, and a WINDOWED read of the thermal band")
    w("")
    w("A whole Landsat scene is ~1 GB. This only works on a free runner if a")
    w("sub-window can be read directly from the COG over HTTPS.")
    w("")

    target = None
    for r in rows:
        if r["cloud"] is not None and r["cloud"] < 25:
            target = r
            break
    target = target or rows[0]
    w("Trying scene `%s` (%s, cloud %s%%)"
      % (target["id"], target["date"], target["cloud"]))
    w("")

    key = None
    for cand in ("lwir11", "ST_B10", "st_b10", "lwir"):
        if cand in target["item"].assets:
            key = cand
            break
    if key is None:
        w("**FAILED**: no thermal asset on this scene. Assets: %s"
          % ", ".join(target["assets"]))
        return flush(False)
    w("Thermal asset key: `%s`" % key)

    item = target["item"]
    signed_href = item.assets[key].href
    try:
        import planetary_computer as pc
        item = pc.sign(item)
        signed_href = item.assets[key].href
        w("Signing: planetary_computer.sign() succeeded")
    except Exception as exc:                                # noqa: BLE001
        w("Signing: not applied (%s). Will try the unsigned href."
          % str(exc)[:90])
    w("")

    try:
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds

        os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
        os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF")

        with rasterio.open(signed_href) as ds:
            w("Opened the COG. size %d x %d, crs %s, dtype %s"
              % (ds.width, ds.height, ds.crs, ds.dtypes[0]))
            left, bottom, right, top = transform_bounds(
                "EPSG:4326", ds.crs, *BBOX, densify_pts=21)
            win = from_bounds(left, bottom, right, top, ds.transform)
            win = win.round_offsets().round_lengths()
            w("Window over the bays: %d x %d pixels"
              % (int(win.width), int(win.height)))
            arr = ds.read(1, window=win).astype("float64")
            res = abs(ds.transform.a)
            w("Pixel size: **%.0f m**" % res)
            w("Bytes actually read: roughly %.1f MB (whole scene would be far more)"
              % (arr.size * 2 / 1e6))

        valid = arr > 0
        if not valid.any():
            w("")
            w("**FAILED**: the window is entirely nodata. Wrong scene footprint?")
            return flush(False)
        k = arr[valid] * ST_SCALE + ST_OFFSET
        c = k - 273.15
        w("")
        w("## 5. What the numbers look like")
        w("")
        w("%d valid pixels of %d in the window (%.0f%%)"
          % (valid.sum(), arr.size, 100 * valid.mean()))
        w("")
        w("| statistic | value |")
        w("|---|---|")
        for lab, v in (("min", np.min(c)), ("1st pct", np.percentile(c, 1)),
                       ("median", np.median(c)), ("99th pct", np.percentile(c, 99)),
                       ("max", np.max(c))):
            w("| %s | %.2f degC |" % (lab, v))
        w("")
        plausible = (-5 < np.percentile(c, 1)) and (np.percentile(c, 99) < 60)
        w("Values in a physically plausible range for land+water: **%s**"
          % ("yes" if plausible else "NO - scaling is wrong"))
        w("")
        w("## Verdict")
        w("")
        w("**VIABLE.** %d m thermal over the bays, windowed read, %d scenes in the"
          % (res, len(rows)))
        w("last %d days and %d of them under 25%% cloud." % (DAYS_BACK, len(clear)))
        w("")
        w("Next: bake the water pixels only (cloud + land masked) into a PNG the")
        w("offshore page can load, the same way the tide field works.")
        return flush(True)

    except Exception as exc:                                # noqa: BLE001
        w("")
        w("**FAILED** during the windowed read:")
        w("")
        w("```")
        w(traceback.format_exc()[-1800:])
        w("```")
        return flush(False)


if __name__ == "__main__":
    sys.exit(main())
