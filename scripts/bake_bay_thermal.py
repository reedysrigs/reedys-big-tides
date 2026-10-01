#!/usr/bin/env python3
"""
Bake a high-resolution water-temperature field for Port Phillip Bay and
Western Port from Landsat thermal imagery.

Why: the existing SST is ~2 km. Port Phillip is about 50 km across, so the bay
is drawn in roughly 25 pixels and everything inside it - the channel edges, the
warm water over the banks, the cold wedge pushing in through the Rip - is
averaged away before it can be drawn.

Resolution, stated honestly: Landsat's TIRS thermal sensor is 100 m. USGS
delivers it resampled onto the 30 m grid shared with the optical bands. The
GRID is 30 m; the INFORMATION is 100 m. This bakes onto a 100 m grid, because
pretending to 30 m detail that was never measured is how a map starts lying.

What it is NOT: this is not a daily product. Landsat passes every ~7 days
(median measured over 180 days) and cloud takes some of those. The JSON records
the scene date and cloud fraction so the page can say plainly how old the
picture is rather than implying it is live.

Masking uses the QA_PIXEL band that ships with every scene - Collection 2 bit
layout:
    0 fill, 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow,
    5 snow, 6 clear, 7 water
Only pixels that are WATER and free of fill/cloud/cirrus/shadow survive. Land
is dropped outright, which is the whole point: the current map's worst pixels
in the bays are the half-land ones reading hot.
"""
import datetime as dt
import json
import os
import sys

import numpy as np

# Port Phillip Bay + Western Port, plus the approaches outside the heads.
WEST, EAST = 144.35, 145.60
SOUTH, NORTH = -38.70, -37.80

# 100 m, which is the real resolution of the thermal sensor.
METRES = 100.0
DEG_LAT = METRES / 110574.0

OUT_PNG = "docs/bay-sst.png"
OUT_JSON = "docs/bay-sst.json"
VERSION = "v1"

ST_SCALE, ST_OFFSET = 0.00341802, 149.0      # DN -> Kelvin, USGS Collection 2
MAX_AGE_DAYS = 45
MAX_CLOUD = 40.0

QA_FILL, QA_DILATED, QA_CIRRUS = 1 << 0, 1 << 1, 1 << 2
QA_CLOUD, QA_SHADOW, QA_WATER = 1 << 3, 1 << 4, 1 << 7


def grid_axes():
    """Cell-centre lon/lat. Row 0 is NORTH, matching the page's textures."""
    dlat = DEG_LAT
    dlon = DEG_LAT / max(0.2, np.cos(np.radians((NORTH + SOUTH) / 2.0)))
    nx = int(round((EAST - WEST) / dlon))
    ny = int(round((NORTH - SOUTH) / dlat))
    lon = WEST + (np.arange(nx) + 0.5) * dlon
    lat = NORTH - (np.arange(ny) + 0.5) * dlat
    return lon, lat


def encode(temp_c, tmin, tmax, grad=None, grad_max=1.0):
    """(H,W) degC with NaN -> (H,W,4) uint8.

    R,G carry a 16-bit fixed-point temperature so the step is ~0.0003 degC and
    quantisation never becomes the thing anyone argues about.
    B carries the temperature GRADIENT, which is the layer that actually
    matters for fishing: a front shows as a bright line whether the water is
    14 degrees or 17. At 2 km a front narrower than a pixel is averaged into
    flat colour and cannot be seen at all; at 100 m it is a line.
    A is the data mask: 255 where there is a real water reading, 0 elsewhere.
        T    = tmin + (R*256 + G) / 65535 * (tmax - tmin)
        grad = B / 255 * grad_max                      degC per km
    """
    t = np.asarray(temp_c, dtype=np.float64)
    ok = np.isfinite(t)
    span = max(1e-6, float(tmax - tmin))
    q = np.clip((np.where(ok, t, tmin) - tmin) / span, 0.0, 1.0)
    n = np.rint(q * 65535.0).astype(np.int64)
    out = np.zeros(t.shape + (4,), dtype=np.uint8)
    out[..., 0] = (n >> 8).astype(np.uint8)
    out[..., 1] = (n & 0xFF).astype(np.uint8)
    if grad is None:
        out[..., 2] = np.rint(q * 255.0).astype(np.uint8)
    else:
        g = np.clip(np.where(np.isfinite(grad), grad, 0.0) / max(1e-6, grad_max),
                    0.0, 1.0)
        out[..., 2] = np.rint(g * 255.0).astype(np.uint8)
    out[..., 3] = np.where(ok, 255, 0).astype(np.uint8)
    return out


def decode(px, tmin, tmax):
    """Exactly what the page must do. Kept here so the pair can be tested."""
    px = np.asarray(px)
    n = px[..., 0].astype(np.float64) * 256.0 + px[..., 1].astype(np.float64)
    t = tmin + n / 65535.0 * (tmax - tmin)
    return t, px[..., 3] >= 128


def gradient_per_km(temp_c, lon, lat):
    """Magnitude of the horizontal temperature gradient, degC per km.

    Computed with one-sided differences at the edges of the valid-data mask so
    a front against a cloud hole or the shoreline does not manufacture a fake
    edge - NaN neighbours simply do not contribute.
    """
    t = np.asarray(temp_c, dtype=np.float64)
    ok = np.isfinite(t)
    filled = np.where(ok, t, 0.0)

    def diff(axis, spacing_km):
        a = np.full_like(t, np.nan)
        f = np.roll(filled, -1, axis=axis)
        b = np.roll(filled, 1, axis=axis)
        fo = np.roll(ok, -1, axis=axis)
        bo = np.roll(ok, 1, axis=axis)
        both = fo & bo & ok
        one_f = fo & ~bo & ok
        one_b = bo & ~fo & ok
        a[both] = (f[both] - b[both]) / (2.0 * spacing_km[both] if
                                         isinstance(spacing_km, np.ndarray)
                                         else 2.0 * spacing_km)
        sf = spacing_km[one_f] if isinstance(spacing_km, np.ndarray) else spacing_km
        sb = spacing_km[one_b] if isinstance(spacing_km, np.ndarray) else spacing_km
        a[one_f] = (f[one_f] - t[one_f]) / sf
        a[one_b] = (t[one_b] - b[one_b]) / sb
        # the wrap-around row/column is meaningless
        sl = [slice(None)] * t.ndim
        sl[axis] = 0
        a[tuple(sl)] = np.nan
        sl[axis] = -1
        a[tuple(sl)] = np.nan
        return a

    dlat_km = abs(float(lat[0] - lat[1])) * 110.574
    dlon_km = (abs(float(lon[1] - lon[0])) * 111.320
               * np.cos(np.radians(lat))[:, None] * np.ones((1, len(lon))))
    dy = diff(0, dlat_km)
    dx = diff(1, dlon_km)
    g = np.hypot(np.where(np.isfinite(dx), dx, 0.0),
                 np.where(np.isfinite(dy), dy, 0.0))
    g[~ok] = np.nan
    return g


def pick_scenes(bbox, days_back=MAX_AGE_DAYS):
    """The newest usable PASS, as a list of scenes from that one date.

    Grouped by date because the bays straddle WRS rows - a single pass is often
    two scenes (row 086 and 087) that have to be mosaicked.
    """
    from pystac_client import Client

    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=days_back)
    cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    items = list(cat.search(
        collections=["landsat-c2-l2"], bbox=bbox,
        datetime="%s/%s" % (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
        limit=200).items())
    if not items:
        raise SystemExit("::error::no Landsat scenes over the bays in %d days"
                         % days_back)

    by_date = {}
    for it in items:
        if "lwir11" not in it.assets or "qa_pixel" not in it.assets:
            continue
        day = (it.properties.get("datetime") or "")[:10]
        by_date.setdefault(day, []).append(it)

    usable = []
    for day, group in by_date.items():
        clouds = [g.properties.get("eo:cloud_cover") for g in group]
        clouds = [c for c in clouds if c is not None]
        mean_cloud = float(np.mean(clouds)) if clouds else 100.0
        if mean_cloud <= MAX_CLOUD:
            usable.append((day, mean_cloud, group))
    if not usable:
        best = min(((d, float(np.mean([g.properties.get("eo:cloud_cover") or 100
                                       for g in grp])), grp)
                    for d, grp in by_date.items()), key=lambda r: r[1])
        raise SystemExit("::error::no pass under %.0f%% cloud in %d days; "
                         "best was %s at %.1f%%"
                         % (MAX_CLOUD, days_back, best[0], best[1]))

    usable.sort(key=lambda r: r[0], reverse=True)
    print("%d usable pass(es) in %d days: %s"
          % (len(usable), days_back,
             ", ".join("%s(%.0f%%)" % (d, c) for d, c, _ in usable[:8])))
    return usable


def read_scene(item, lon, lat):
    """Water temperature in degC from one scene, on the output grid. NaN elsewhere."""
    import planetary_computer as pc
    import rasterio
    from rasterio.warp import transform_bounds, reproject, Resampling
    from rasterio.windows import from_bounds
    from rasterio.transform import from_origin

    item = pc.sign(item)
    dlon = float(lon[1] - lon[0])
    dlat = float(lat[0] - lat[1])
    dst_transform = from_origin(lon[0] - dlon / 2.0, lat[0] + dlat / 2.0, dlon, dlat)
    dst = np.full((len(lat), len(lon)), np.nan, dtype="float32")

    with rasterio.open(item.assets["lwir11"].href) as src:
        l, b, r, t = transform_bounds("EPSG:4326", src.crs,
                                      WEST, SOUTH, EAST, NORTH, densify_pts=21)
        win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
        # Clip the window to the scene, or rasterio reads off the edge.
        win = win.intersection(
            rasterio.windows.Window(0, 0, src.width, src.height))
        if win.width < 2 or win.height < 2:
            return dst, 0
        therm = src.read(1, window=win).astype("float32")
        src_transform = src.window_transform(win)
        src_crs = src.crs

    with rasterio.open(pc.sign(item).assets["qa_pixel"].href) as q:
        qa = q.read(1, window=win)

    bad = (qa & (QA_FILL | QA_DILATED | QA_CIRRUS | QA_CLOUD | QA_SHADOW)) != 0
    water = (qa & QA_WATER) != 0
    keep = water & ~bad & (therm > 0)
    if not keep.any():
        return dst, 0

    celsius = np.where(keep, therm * ST_SCALE + ST_OFFSET - 273.15, np.nan)
    celsius = celsius.astype("float32")

    reproject(source=celsius, destination=dst,
              src_transform=src_transform, src_crs=src_crs,
              dst_transform=dst_transform, dst_crs="EPSG:4326",
              src_nodata=np.nan, dst_nodata=np.nan,
              resampling=Resampling.average)
    return dst, int(keep.sum())


def mosaic(group, lon, lat):
    """All scenes from one pass, merged onto the output grid."""
    stack = np.full((len(lat), len(lon)), np.nan, dtype="float32")
    for it in group:
        try:
            arr, n = read_scene(it, lon, lat)
        except Exception as exc:                            # noqa: BLE001
            print("  scene %s failed: %s" % (it.id, exc), file=sys.stderr)
            continue
        print("  %s -> %d water pixels" % (it.id, n))
        fill = np.isnan(stack) & np.isfinite(arr)
        stack[fill] = arr[fill]
    return stack


def main():
    lon, lat = grid_axes()
    print("grid %d x %d at %.0f m" % (len(lat), len(lon), METRES))

    passes = pick_scenes([WEST, SOUTH, EAST, NORTH])
    day, cloud, group = passes[0]
    print("latest pass %s, %d scene(s), mean cloud %.1f%%"
          % (day, len(group), cloud))
    stack = mosaic(group, lon, lat)

    ok = np.isfinite(stack)
    frac = float(ok.mean())
    print("water coverage of the box: %.1f%% (%d cells)" % (100 * frac, ok.sum()))
    if ok.sum() < 20000:
        print("::error::only %d water cells - cloud or masking took the bays out"
              % ok.sum(), file=sys.stderr)
        return 1

    t = stack[ok]
    tmin = float(np.floor(np.percentile(t, 0.2) * 2) / 2 - 0.5)
    tmax = float(np.ceil(np.percentile(t, 99.8) * 2) / 2 + 0.5)

    # The fronts. This is the layer worth having - at 2 km a front narrower
    # than a pixel is averaged into flat colour and cannot be seen at all.
    grad = gradient_per_km(stack, lon, lat)
    gok = np.isfinite(grad)
    grad_max = float(np.percentile(grad[gok], 99.5)) if gok.any() else 1.0
    grad_max = max(0.05, grad_max)
    px = encode(stack, tmin, tmax, grad=grad, grad_max=grad_max)

    # Which way the warm water is pushing: difference against the most recent
    # earlier pass that is far enough back to mean something.
    delta_meta = None
    prev = next((p for p in passes[1:]
                 if (dt.datetime.strptime(day, "%Y-%m-%d")
                     - dt.datetime.strptime(p[0], "%Y-%m-%d")).days >= 5), None)
    if prev is None:
        print("no earlier usable pass at least 5 days back - skipping the "
              "change layer this run")
    else:
        pday, pcloud, pgroup = prev
        gap = (dt.datetime.strptime(day, "%Y-%m-%d")
               - dt.datetime.strptime(pday, "%Y-%m-%d")).days
        print("previous pass %s (%.0f%% cloud), %d days earlier"
              % (pday, pcloud, gap))
        pstack = mosaic(pgroup, lon, lat)
        both = ok & np.isfinite(pstack)
        if both.sum() < 5000:
            print("only %d cells common to both passes - skipping the change "
                  "layer" % both.sum())
        else:
            d = np.where(both, stack - pstack, np.nan)
            dv = d[both]
            dmax = float(max(0.5, np.percentile(np.abs(dv), 99.0)))
            # signed, so 128 is no change; red warmer, blue cooler on the page
            dq = np.clip(np.where(both, d, 0.0) / dmax, -1.0, 1.0)
            dpx = np.zeros(d.shape + (4,), dtype=np.uint8)
            n16 = np.rint((dq + 1.0) / 2.0 * 65535.0).astype(np.int64)
            dpx[..., 0] = (n16 >> 8).astype(np.uint8)
            dpx[..., 1] = (n16 & 0xFF).astype(np.uint8)
            dpx[..., 2] = np.rint(np.abs(dq) * 255.0).astype(np.uint8)
            dpx[..., 3] = np.where(both, 255, 0).astype(np.uint8)
            from PIL import Image as _Im
            os.makedirs("docs", exist_ok=True)
            _Im.fromarray(dpx, "RGBA").save("docs/bay-sst-delta.png", optimize=True)
            delta_meta = {
                "version": VERSION,
                "from_date": pday, "to_date": day, "days": gap,
                "d_max_c": round(dmax, 3),
                "decode": "dC = ((R*256+G)/65535*2 - 1) * d_max_c",
                "width": len(lon), "height": len(lat),
                "bounds": {"west": float(lon[0]), "east": float(lon[-1]),
                           "south": float(lat[-1]), "north": float(lat[0])},
                "cells": int(both.sum()),
                "warmed_pct": round(100.0 * float((dv > 0.2).mean()), 1),
                "cooled_pct": round(100.0 * float((dv < -0.2).mean()), 1),
                "median_change_c": round(float(np.median(dv)), 3),
            }
            with open("docs/bay-sst-delta.json", "w") as fh:
                json.dump(delta_meta, fh, separators=(",", ":"))
            print("wrote docs/bay-sst-delta.png  %s -> %s (%d days)  "
                  "warmed %.0f%%  cooled %.0f%%  median %+.2f degC"
                  % (pday, day, gap, delta_meta["warmed_pct"],
                     delta_meta["cooled_pct"], delta_meta["median_change_c"]))

    scene_dt = (group[0].properties.get("datetime") or day)[:19] + "Z"
    meta = {
        "version": VERSION,
        "source": "Landsat 8/9 TIRS surface temperature (USGS Collection 2 Level-2)",
        "licence": "USGS Landsat - public domain, courtesy of the U.S. Geological Survey",
        "scene_time": scene_dt,
        "scene_date": day,
        "scene_ids": [g.id for g in group],
        "cloud_cover_pct": round(cloud, 1),
        "age_days": (dt.datetime.utcnow() - dt.datetime.strptime(day, "%Y-%m-%d")).days,
        "generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "width": len(lon), "height": len(lat),
        "bounds": {"west": float(lon[0]), "east": float(lon[-1]),
                   "south": float(lat[-1]), "north": float(lat[0])},
        "grid_metres": METRES,
        "sensor_metres": 100,
        "note": "Thermal sensor is 100 m; USGS resamples onto a 30 m grid. "
                "This is baked at 100 m, the real resolution.",
        "t_min": tmin, "t_max": tmax,
        "quantisation_c": round((tmax - tmin) / 65535.0, 5),
        # The fronts layer, carried in the blue channel.
        "grad_max_c_per_km": round(grad_max, 4),
        "grad_decode": "degC_per_km = B / 255 * grad_max_c_per_km",
        "grad_p99_5_c_per_km": round(grad_max, 4),
        "decode": "degC = t_min + (R*256+G)/65535 * (t_max - t_min)",
        "change_layer": ("bay-sst-delta.png" if delta_meta else None),
        "change": delta_meta,
        "observed_min_c": round(float(t.min()), 2),
        "observed_max_c": round(float(t.max()), 2),
        "median_c": round(float(np.median(t)), 2),
        "water_fraction": round(frac, 4),
        "water_cells": int(ok.sum()),
        "skin_temperature": True,
    }

    from PIL import Image
    os.makedirs("docs", exist_ok=True)
    Image.fromarray(px, "RGBA").save(OUT_PNG, optimize=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))

    print("wrote %s  %dx%d  %s (%d days old, %.0f%% cloud)  water %.0f%%  "
          "median %.2f degC  range %.2f..%.2f"
          % (OUT_PNG, len(lon), len(lat), day, meta["age_days"], cloud,
             100 * frac, meta["median_c"], meta["observed_min_c"],
             meta["observed_max_c"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
