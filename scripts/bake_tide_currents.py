#!/usr/bin/env python3
"""
Bake a tidal-current u/v field for Australian waters into docs/tide-uv.png
plus docs/tide-uv.json, in exactly the encoding reedysrigs.com/offshore/ decodes.

Source: FES2014 tidal current constituents (Carrere et al.), via pyTMD.
Licence: FES2014 is delivered for all purposes including commercial, with
attribution.  See AVISO FES licence.

Why this exists: the existing current-uv field is HYCOM, ~13.9 km cells at
Bass Strait latitudes.  FES2014 is 1/16 degree - about 5.4 km of longitude at
-38.5, so roughly 2.6x finer linearly and 6.6x finer by area.

What it does NOT do, measured on the first real bake rather than assumed:

  - It does not resolve Port Phillip Heads.  The Rip is 3.2 km across and the
    cell containing it has no data at all; the nearest cell with data is 4.4 km
    away.  The BoM tidal stream table (scripts/parse_bom_rip.py) remains the
    only usable source there, and being observation-derived it is better than
    any model would be.
  - It does not resolve the Western Port entrance either - nearest data 8.8 km
    away - and BoM publishes no stream table for Western Port.  Tidal current
    inside Western Port is therefore still unsolved; do not pretend otherwise.
  - An earlier version of this comment claimed FES "has values right into the
    coast".  That was wrong and is corrected here.  Coverage over the box is
    66.9%, which is close to HYCOM's 67.3% - the masked third is mostly the
    continent, in both models.  The gain is resolution, not reach.

Where it is genuinely good is open water: 10 of 10 offshore test points from
the Portland canyons to the Tasman carry data, and the model independently puts
Australia's fastest tidal water at the Horizontal Falls (6.06 kn), Broad Sound
and Arnhem Land - the three largest tidal-range areas in the country.

The PNG encoding, which MUST match the shader in the offshore page:
    R = (u / u_range + 1) / 2 * 255      eastward,  m/s
    G = (v / v_range + 1) / 2 * 255      northward, m/s
    B = speed / speed_ref * 255          display only
    A = 255 where there is data, 0 where there is not
"""
import json, os, sys, math, datetime as dt
import numpy as np

# ---------------------------------------------------------------- grid
# Same box as the HYCOM field so the two can be blended cell-for-cell,
# at twice the linear resolution: 0.08 x 0.04 deg  (~7.0 x 4.4 km at -38.5)
WEST, EAST = 108.0, 162.88
SOUTH, NORTH = -48.0, -8.0
WIDTH, HEIGHT = 688, 1002

OUT_PNG = "docs/tide-uv.png"
OUT_JSON = "docs/tide-uv.json"
VERSION = "v1"
MODEL = "FES2014"


def grid_axes():
    """Cell-centre longitudes and latitudes. Row 0 is NORTH, matching the
    page, which maps texture y=0 to bounds.north."""
    lon = np.linspace(WEST, EAST, WIDTH)
    lat = np.linspace(NORTH, SOUTH, HEIGHT)
    return lon, lat


# ---------------------------------------------------------------- encode
def encode(u, v, u_range, v_range, speed_ref):
    """u, v in m/s, NaN where there is no data. Returns (H,W,4) uint8.

    Kept free of I/O and of pyTMD so it can be tested on its own.
    """
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if u.shape != v.shape:
        raise ValueError("u and v must have the same shape")
    ok = np.isfinite(u) & np.isfinite(v)

    uc = np.clip(np.where(ok, u, 0.0), -u_range, u_range)
    vc = np.clip(np.where(ok, v, 0.0), -v_range, v_range)

    r = np.rint((uc / u_range + 1.0) / 2.0 * 255.0)
    g = np.rint((vc / v_range + 1.0) / 2.0 * 255.0)
    spd = np.hypot(uc, vc)
    b = np.rint(np.clip(spd / speed_ref, 0.0, 1.0) * 255.0)

    out = np.zeros(u.shape + (4,), dtype=np.uint8)
    out[..., 0] = np.clip(r, 0, 255).astype(np.uint8)
    out[..., 1] = np.clip(g, 0, 255).astype(np.uint8)
    out[..., 2] = np.clip(b, 0, 255).astype(np.uint8)
    out[..., 3] = np.where(ok, 255, 0).astype(np.uint8)
    return out


def decode(px, u_range, v_range):
    """Exactly what the page's rrFlowAt() does, for verification."""
    px = np.asarray(px)
    u = (px[..., 0] / 255.0 * 2.0 - 1.0) * u_range
    v = (px[..., 1] / 255.0 * 2.0 - 1.0) * v_range
    water = px[..., 3] >= 128
    return u, v, water


# ---------------------------------------------------------------- model
# pyTMD's own FES2014 database entry cannot be used here, for two reasons,
# both verified rather than assumed:
#
#   1. model.from_database() runs pathfinder() over EVERY group it knows,
#      including 'z' (ocean_tide/).  We only download the two current
#      archives, so it raises FileNotFoundError on fes2014/ocean_tide/2n2.nc
#      before it ever looks at a current file.  Writing our own definition
#      file with only u and v avoids a third 2 GB download we have no use for.
#
#   2. It hard-codes all 34 constituents, so a single missing file is fatal.
#      Building the list from what is actually on disk means a partial fetch
#      is reported honestly below instead of dying inside pyTMD.
#
# Definition-file format is pyTMD's own JSON, matching its FES2014 entry.
U_SUBDIR, V_SUBDIR = "eastward_velocity", "northward_velocity"

# Every constituent FES2014 publishes. The two current archives contain all of
# them, so a healthy fetch produces exactly this set.
FES2014_ALL = (
    "2n2 eps2 j1 k1 k2 l2 la2 m2 m3 m4 m6 m8 mf mks2 mm mn4 ms4 msf msqm mtm "
    "mu2 n2 n4 nu2 o1 p1 q1 r2 s1 s2 s4 sa ssa t2"
).split()

# Filled in by tidal_currents() so the metadata can state exactly what the
# field was built from, rather than what we hoped it was built from.
RUN_INFO = {}


def present_constituents(directory):
    """Constituents with BOTH a u and a v file under `directory`. Sorted."""
    root = os.path.join(directory, "fes2014")
    def names(sub):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            return set()
        return {f[:-3] for f in os.listdir(d) if f.endswith(".nc")}
    u, v = names(U_SUBDIR), names(V_SUBDIR)
    both = sorted(u & v)
    only_u, only_v = sorted(u - v), sorted(v - u)
    if only_u or only_v:
        print("WARNING: unpaired constituents ignored - u-only %r, v-only %r"
              % (only_u, only_v), file=sys.stderr)
    return both


def write_definition(path, constituents):
    """pyTMD JSON definition for FES2014 currents, u and v groups only."""
    spec = {
        "format": "FES-netcdf",
        "name": "FES2014-currents-AU",
        "version": "FES2014",
        "reference": "https://www.aviso.altimetry.fr/en/data/products"
                     "auxiliary-products/global-tide-fes.html",
        "projection": {"datum": "WGS84", "ellps": "WGS84", "lon_wrap": 180,
                       "proj": "longlat", "type": "crs"},
        "u": {"model_file": ["fes2014/%s/%s.nc" % (U_SUBDIR, c)
                             for c in constituents],
              "units": "cm/s", "variable": "zonal_tidal_current"},
        "v": {"model_file": ["fes2014/%s/%s.nc" % (V_SUBDIR, c)
                             for c in constituents],
              "units": "cm/s", "variable": "meridional_tidal_current"},
    }
    with open(path, "w") as fh:
        json.dump(spec, fh, indent=1)
    return path


def tidal_currents(when, directory):
    """u, v in m/s on the output grid at UTC time `when`. NaN over land."""
    import pyTMD.compute

    cons = present_constituents(directory)
    if len(cons) < 8:
        raise SystemExit("::error::only %d paired constituents on disk (%r); "
                         "need at least the 8 principal ones"
                         % (len(cons), cons))
    print("using %d constituents: %s" % (len(cons), " ".join(cons)))

    # pyTMD infers the minor constituents by default, and that inference reads
    # specific majors by name - _infer_short_period() does
    #     dmin["eps2"] = 0.53285 * ds["2n2"] - 0.03304 * ds["n2"]
    # so a set missing 2n2 dies with KeyError: '2n2' deep inside predict/.
    # With the complete 34 it is fine (verified).  With anything less, turn the
    # inference off rather than crash: slightly coarser, still a usable field,
    # and the metadata records what was actually used.
    missing = [c for c in FES2014_ALL if c not in cons]
    infer_minor = not missing
    RUN_INFO["constituents"] = cons
    RUN_INFO["missing"] = missing
    RUN_INFO["infer_minor"] = infer_minor
    if missing:
        print("WARNING: missing %d constituent(s): %s" % (len(missing), " ".join(missing)),
              file=sys.stderr)
        print("WARNING: minor-constituent inference disabled - it needs the full set",
              file=sys.stderr)

    defn = write_definition(os.path.join(directory, "fes2014-currents.json"), cons)

    lon, lat = grid_axes()
    epoch = (2000, 1, 1, 0, 0, 0)
    t0 = dt.datetime(*epoch, tzinfo=dt.timezone.utc)
    delta = np.array([(when - t0).total_seconds()])

    # method: pyTMD 3.0.9 accepts only 'linear' and 'nearest'.  'spline' raises
    # ValueError("Unknown interpolation method") - it is not a valid option here.
    #
    # No crop=True: the constituent files on disk are ALREADY cropped to this
    # box by scripts/crop_fes.py during the fetch, so pyTMD's own crop would
    # re-do work for nothing - and it goes through ds.chunk(), which raises
    # ImportError("chunk manager 'dask' is not available") unless dask is
    # installed.  Dropping it removes both the overhead and the dependency.
    common = dict(
        directory=directory, definition_file=defn, type="grid",
        epoch=epoch, standard="UTC", method="linear",
        infer_minor=infer_minor,
    )
    out = pyTMD.compute.tide_currents(lon, lat, delta, **common)

    def take(key):
        a = out[key] if isinstance(out, dict) else getattr(out, key)
        a = np.ma.filled(np.asarray(a, dtype=np.float64), np.nan)
        a = np.squeeze(a)
        if a.shape != (HEIGHT, WIDTH):
            if a.shape == (WIDTH, HEIGHT):
                a = a.T
            else:
                raise ValueError("unexpected %s shape %r, wanted %r"
                                 % (key, a.shape, (HEIGHT, WIDTH)))
        return a

    # FES2014 currents are published in cm/s; pyTMD carries those units through.
    return take("u") / 100.0, take("v") / 100.0


# ---------------------------------------------------------------- write
def write(px, meta):
    from PIL import Image
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    Image.fromarray(px, "RGBA").save(OUT_PNG, optimize=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))


def main():
    directory = os.environ.get("FES_DIR", "fes-data")
    when = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)

    u, v = tidal_currents(when, directory)

    ok = np.isfinite(u) & np.isfinite(v)
    if not ok.any():
        print("FAILED: the model returned no water anywhere", file=sys.stderr)
        return 1
    water_fraction = float(ok.mean())
    if water_fraction < 0.35:
        print("FAILED: only %.1f%% of the box has data, expected well over 35%%"
              % (100 * water_fraction), file=sys.stderr)
        return 1

    spd = np.hypot(np.where(ok, u, 0.0), np.where(ok, v, 0.0))

    # The 99.9th-percentile clip this used to carry was borrowed from the SST
    # fit, and it is wrong for tidal currents.  SST is narrowly distributed;
    # tidal current is violently heavy-tailed - nearly all of the ocean is slow
    # and the interesting water is in a handful of narrow passages.  On the real
    # field the clip came out at 0.74 m/s while the model reached 2.62 m/s, so
    # the PNG saturated at 1.98 kn and threw away EVERY tidal race - the exact
    # feature worth having.  Worse, the metadata still reported speed_max as
    # 6.06 kn, which described the field before encoding, not the one shipped.
    #
    # So: encode the real range.  The cap is only a guard against a single rogue
    # cell in some narrow channel flattening the scale for everything else, and
    # it is recorded below along with how many cells it actually touched.
    CEILING = 3.5                                   # m/s, ~6.8 kn
    u_range = float(min(max(0.25, np.abs(u[ok]).max()), CEILING))
    v_range = float(min(max(0.25, np.abs(v[ok]).max()), CEILING))
    speed_ref = float(min(max(0.30, spd[ok].max()), CEILING))
    clipped = int(((np.abs(u) > u_range) | (np.abs(v) > v_range))[ok].sum())

    px = encode(u, v, u_range, v_range, speed_ref)

    meta = {
        "version": VERSION,
        "source": "FES2014 tidal currents (Carrere et al.), via pyTMD",
        "licence": "FES2014 - all purposes including commercial, with attribution",
        "generated": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "width": WIDTH, "height": HEIGHT,
        "bounds": {"west": WEST, "east": EAST, "south": SOUTH, "north": NORTH},
        "u_range": u_range, "v_range": v_range,
        "speed_max": float(spd[ok].max()),
        "speed_ref": speed_ref,
        "observed_max_u": float(np.abs(u[ok]).max()),
        "observed_max_v": float(np.abs(v[ok]).max()),
        # What the PNG can actually represent, as opposed to what the model
        # produced. These two used to disagree by a factor of three with
        # nothing saying so.
        "encoded_ceiling_ms": round(float(np.hypot(u_range, v_range)), 4),
        "encoded_ceiling_kn": round(float(np.hypot(u_range, v_range) * 1.94384), 3),
        "speed_max_kn": round(float(spd[ok].max() * 1.94384), 3),
        "clipped_cells": clipped,
        "quantisation_ms": round(float(2 * u_range / 255), 5),
        "quantisation_kn": round(float(2 * u_range / 255 * 1.94384), 4),
        "clip_ceiling_ms": CEILING,
        "water_fraction": round(water_fraction, 3),
        "tide_only": True,
        "constituents": RUN_INFO.get("constituents", []),
        "constituent_count": len(RUN_INFO.get("constituents", [])),
        "missing_constituents": RUN_INFO.get("missing", []),
        "infer_minor": RUN_INFO.get("infer_minor", False),
    }
    write(px, meta)
    print("wrote %s  %dx%d  water %.1f%%  max %.2f m/s (%.1f kn)"
          % (OUT_PNG, WIDTH, HEIGHT, 100 * water_fraction,
             meta["speed_max"], meta["speed_max"] * 1.94384))
    return 0


if __name__ == "__main__":
    sys.exit(main())
