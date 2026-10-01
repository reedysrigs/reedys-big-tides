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

# A physical floor and ceiling for water in these two bays. Measured on the
# first real bake: 99.4% of the pixels QA_PIXEL called water came back between
# 8 and 24 degC with a median of 13.64, and the remaining 0.6% sat below 8 -
# cloud shadow the quality band did not catch. Those few hundredths of a
# percent were enough to drag the gradient scale to 14.6 degC/km and flatten
# the layer that matters, so they are cut on physical grounds and the count is
# reported rather than hidden.
PHYS_MIN_C, PHYS_MAX_C = 6.0, 26.0


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


SMOOTH_RADIUS = 2       # 5x5 boxcar, ~500 m
GRAD_BASELINE = 3       # differences over +/-3 cells, ~600 m


def _nan_boxcar(t, ok, r):
    """Mean over a (2r+1)^2 window, ignoring NaN. Separable, via summed areas."""
    v = np.where(ok, t, 0.0)
    w = ok.astype(np.float64)

    def run(a):
        c = np.cumsum(a, axis=0)
        c = np.vstack([np.zeros((1, a.shape[1])), c])
        lo = np.clip(np.arange(a.shape[0]) - r, 0, a.shape[0])
        hi = np.clip(np.arange(a.shape[0]) + r + 1, 0, a.shape[0])
        out = c[hi] - c[lo]
        c2 = np.cumsum(out, axis=1)
        c2 = np.hstack([np.zeros((out.shape[0], 1)), c2])
        lo2 = np.clip(np.arange(a.shape[1]) - r, 0, a.shape[1])
        hi2 = np.clip(np.arange(a.shape[1]) + r + 1, 0, a.shape[1])
        return c2[:, hi2] - c2[:, lo2]

    s, n = run(v), run(w)
    out = np.full_like(t, np.nan)
    good = n > 0
    out[good] = s[good] / n[good]
    return out


def gradient_per_km(temp_c, lon, lat):
    """Magnitude of the horizontal temperature gradient, degC per km.

    Smoothed first, and differenced over a baseline of several cells, because
    at single-pixel spacing this measures the SENSOR, not the water. TIRS has
    radiometric noise around 0.1 degC; across one 100 m cell that is already
    1.0 degC/km, against a measured whole-bay median of 0.37. The first version
    of this layer rendered as uniform speckle for exactly that reason - it was
    a picture of detector noise.

    A 5x5 mean cuts the noise about fivefold and a 600 m baseline divides it
    again, which puts the noise floor near 0.05 degC/km while leaving real
    fronts - which run over hundreds of metres to kilometres - untouched.

    One-sided differences at the edge of the valid-data mask, so a front
    against a cloud hole or the shoreline does not manufacture a fake edge.
    """
    t0 = np.asarray(temp_c, dtype=np.float64)
    ok0 = np.isfinite(t0)
    t = _nan_boxcar(t0, ok0, SMOOTH_RADIUS)
    ok = np.isfinite(t) & ok0
    t = np.where(ok, t, np.nan)
    filled = np.where(ok, t, 0.0)

    def diff(axis, spacing_km):
        k = GRAD_BASELINE
        spacing_km = spacing_km * k          # the baseline, not one cell
        a = np.full_like(t, np.nan)
        f = np.roll(filled, -k, axis=axis)
        b = np.roll(filled, k, axis=axis)
        fo = np.roll(ok, -k, axis=axis)
        bo = np.roll(ok, k, axis=axis)
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
        sl[axis] = slice(0, GRAD_BASELINE)
        a[tuple(sl)] = np.nan
        sl[axis] = slice(-GRAD_BASELINE, None)
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

    # Newest is NOT best. The first real bake took 2026-09-27 at 23% cloud
    # because it was 4 days old, over 2026-09-20 at 0.0% cloud seven days
    # earlier - and the result had holes through half of Port Phillip: the
    # west-central bay came out 35% covered against 92% in the centre. For a
    # product whose whole purpose is seeing structure, a clear picture a week
    # old beats a cloudy one from Tuesday. So: among recent passes, take the
    # clearest, and only use age to break a tie.
    #
    # And cloud is not the only thing that leaves holes. Landsat flies fixed
    # swaths: WRS path 092 covers the eastern side of the bay, 093 the western.
    # The 0%-cloud pass of 2026-09-20 was path 092, so west-central Port
    # Phillip came out 29% covered while the centre was 98% - nothing to do
    # with cloud. So score a pass by how much of the BAY its scene footprints
    # actually reach, from the STAC geometry, before downloading anything.
    FRESH_DAYS = 28
    today = dt.datetime.utcnow()

    def footprint_cover(group):
        """Fraction of the bay box covered by the union of scene bboxes."""
        gx = np.linspace(144.45, 145.00, 60)
        gy = np.linspace(-38.35, -37.87, 60)
        X, Y = np.meshgrid(gx, gy)
        hit = np.zeros(X.shape, dtype=bool)
        # The real footprint, not the bbox. Landsat scenes are rotated
        # parallelograms, so a bbox can report 100% cover over the bay while
        # the actual swath misses a third of it - which is exactly what the
        # bbox version of this check did on path 092.
        try:
            from shapely.geometry import shape, Point
            for it in group:
                if not it.geometry:
                    continue
                poly = shape(it.geometry)
                for i in range(X.shape[0]):
                    for j in range(X.shape[1]):
                        if not hit[i, j] and poly.contains(Point(X[i, j], Y[i, j])):
                            hit[i, j] = True
        except ImportError:
            for it in group:
                bb = it.bbox or []
                if len(bb) >= 4:
                    hit |= ((X >= bb[0]) & (X <= bb[2])
                            & (Y >= bb[1]) & (Y <= bb[3]))
        return float(hit.mean())

    recent = [p for p in passes
              if (today - dt.datetime.strptime(p[0], "%Y-%m-%d")).days <= FRESH_DAYS]
    pool = recent or passes[:4]
    scored = []
    for d, c, g in pool:
        cov = footprint_cover(g)
        age = (today - dt.datetime.strptime(d, "%Y-%m-%d")).days
        # coverage first (in 10% bands), then cloud (5% bands), then freshness
        scored.append(((-round(cov * 10), round(c / 5.0), age), d, c, g, cov))
    scored.sort(key=lambda r: r[0])
    _, day, cloud, group, cov = scored[0]
    best = (day, cloud, group)
    print("candidate passes (coverage / cloud / age):")
    for k, d, c, g, cv in scored[:6]:
        print("   %s  cover %3.0f%%  cloud %3.0f%%  age %2dd%s"
              % (d, 100 * cv, c, k[2], "   <- chosen" if d == day else ""))
    print("pass %s, %d scene(s), cloud %.1f%%, footprint cover %.0f%%"
          % (day, len(group), cloud, 100 * cov))
    # Everything older than the chosen pass is a candidate for the change layer.
    passes = [p for p in passes
              if dt.datetime.strptime(p[0], "%Y-%m-%d")
              < dt.datetime.strptime(day, "%Y-%m-%d")]
    passes.insert(0, best)
    stack = mosaic(group, lon, lat)

    raw_cells = int(np.isfinite(stack).sum())
    outside = np.isfinite(stack) & ((stack < PHYS_MIN_C) | (stack > PHYS_MAX_C))
    n_out = int(outside.sum())
    stack[outside] = np.nan
    print("physical filter %.0f-%.0f degC removed %d of %d flagged cells (%.2f%%)"
          % (PHYS_MIN_C, PHYS_MAX_C, n_out, raw_cells,
             100.0 * n_out / max(1, raw_cells)))

    ok = np.isfinite(stack)
    frac = float(ok.mean())
    _ci = np.where((lon >= 144.45) & (lon <= 145.00))[0]
    _ri = np.where((lat >= -38.35) & (lat <= -37.87))[0]
    bay_cov = 100.0 * float(ok[np.ix_(_ri, _ci)].mean()) if len(_ci) and len(_ri) else 0.0
    print("Port Phillip Bay coverage: %.1f%% (the bay is ~85%% water, so this "
          "is the number a cloudy pass costs)" % bay_cov)
    print("water coverage of the box: %.1f%% (%d cells)" % (100 * frac, ok.sum()))
    if ok.sum() < 20000:
        print("::error::only %d water cells - cloud or masking took the bays out"
              % ok.sum(), file=sys.stderr)
        return 1

    t = stack[ok]
    tmin = float(np.floor(np.percentile(t, 0.2) * 2) / 2 - 0.5)
    tmax = float(np.ceil(np.percentile(t, 99.8) * 2) / 2 + 0.5)

    # The structure in these bays lives in TENTHS of a degree - measured
    # interquartile spread across the whole of Port Phillip was 0.31 degC. The
    # 16-bit encoding means no precision is lost whatever the range, but a page
    # that ramps colour naively from t_min to t_max would render all of that as
    # one flat wash. So publish the percentiles and let the page stretch to the
    # water that is actually there.
    pct = {("p%g" % p): round(float(np.percentile(t, p)), 3)
           for p in (0.5, 1, 2, 5, 10, 25, 50, 75, 90, 95, 98, 99, 99.5)}
    iqr = pct["p75"] - pct["p25"]
    print("water %.2f..%.2f degC, median %.2f, IQR %.3f degC "
          "(p2 %.2f, p98 %.2f - stretch display to these)"
          % (t.min(), t.max(), pct["p50"], iqr, pct["p2"], pct["p98"]))

    # The fronts. This is the layer worth having - at 2 km a front narrower
    # than a pixel is averaged into flat colour and cannot be seen at all.
    #
    # But a gradient taken within a couple of cells of land or a cloud hole is
    # not a front, it is the edge of the mask. Measured on the real bake:
    #   interior water      median 0.381 degC/km, 99th pct 5.88
    #   within 2 of an edge median 2.122 degC/km, 99th pct 13.87
    # Left alone, that 14.5% of cells sets the entire colour scale and the
    # layer draws a coastline instead of a front. So the gradient is reported
    # only where there is real water for two cells in every direction.
    grad = gradient_per_km(stack, lon, lat)
    interior = ok.copy()
    for dy in (-2, -1, 1, 2):
        for dx in (-2, -1, 1, 2):
            interior &= np.roll(np.roll(ok, dy, axis=0), dx, axis=1)
    interior[:2, :] = interior[-2:, :] = False
    interior[:, :2] = interior[:, -2:] = False
    grad = np.where(interior, grad, np.nan)
    gok = np.isfinite(grad)
    grad_max = float(np.percentile(grad[gok], 99.0)) if gok.any() else 1.0
    grad_max = max(0.05, grad_max)
    print("fronts: %d interior cells (%.0f%% of water), median %.3f, "
          "99th pct %.3f degC/km"
          % (gok.sum(), 100.0 * gok.sum() / max(1, ok.sum()),
             float(np.median(grad[gok])) if gok.any() else 0.0, grad_max))
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
        "grad_interior_only": True,
        "grad_note": ("Gradient is reported only where there is water for two "
                      "cells in every direction. Within two cells of land or a "
                      "cloud hole a gradient is the edge of the mask, not a "
                      "front, and those cells otherwise set the whole scale."),
        "grad_median_c_per_km": (round(float(np.median(grad[gok])), 4)
                                 if gok.any() else None),
        "grad_cells": int(gok.sum()),
        "decode": "degC = t_min + (R*256+G)/65535 * (t_max - t_min)",
        "change_layer": ("bay-sst-delta.png" if delta_meta else None),
        "change": delta_meta,
        "observed_min_c": round(float(t.min()), 2),
        "observed_max_c": round(float(t.max()), 2),
        "median_c": round(float(np.median(t)), 2),
        # For display. The interesting variation here is a few tenths of a
        # degree, so a page must stretch to these, not to t_min..t_max.
        "percentiles_c": pct,
        "iqr_c": round(float(iqr), 3),
        "display_lo_c": pct["p2"],
        "display_hi_c": pct["p98"],
        "physical_filter_c": [PHYS_MIN_C, PHYS_MAX_C],
        "physical_filter_removed": n_out,
        "physical_filter_removed_pct": round(100.0 * n_out / max(1, raw_cells), 3),
        "water_fraction": round(frac, 4),
        "water_cells": int(ok.sum()),
        # Coverage of the bay itself, which is what a cloudy pass actually
        # costs. The box includes a lot of land, so water_fraction alone hides
        # a hole straight through Port Phillip.
        "bay_coverage_pct": round(bay_cov, 1),
        "footprint_cover_pct": round(100 * cov, 1),
        "wrs_paths": sorted({str(g.properties.get("landsat:wrs_path")) for g in group}),
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
