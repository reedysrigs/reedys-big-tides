#!/usr/bin/env python3
"""
Bake a tidal-current u/v field for Australian waters into docs/tide-uv.png
plus docs/tide-uv.json, in exactly the encoding reedysrigs.com/offshore/ decodes.

Source: FES2014 tidal current constituents (Carrere et al.), via pyTMD.
Licence: FES2014 is delivered for all purposes including commercial, with
attribution.  See AVISO FES licence.

Why this exists: the existing current-uv field is HYCOM, ~13.9 km cells at
Bass Strait latitudes, with a third of the box masked as land/no-data.  It
cannot represent tide-driven coastal flow.  FES2014 is 1/16 degree and has
values right into the coast.

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
def tidal_currents(when, directory):
    """u, v in m/s on the output grid at UTC time `when`. NaN over land."""
    import pyTMD.compute

    lon, lat = grid_axes()
    epoch = (2000, 1, 1, 0, 0, 0)
    t0 = dt.datetime(*epoch, tzinfo=dt.timezone.utc)
    delta = np.array([(when - t0).total_seconds()])

    common = dict(
        directory=directory, model=MODEL, type="grid",
        epoch=epoch, standard="UTC", method="spline",
        crop=True, bounds=[WEST, EAST, SOUTH, NORTH], buffer=1.0,
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
    # Clip the tails so a handful of extreme cells in narrow passages do not
    # flatten the colour ramp everywhere else. Same idea as the SST fit.
    u_range = float(max(0.25, np.percentile(np.abs(u[ok]), 99.9)))
    v_range = float(max(0.25, np.percentile(np.abs(v[ok]), 99.9)))
    speed_ref = float(max(0.30, np.percentile(spd[ok], 99.9)))

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
        "clip_percentile": 99.9,
        "water_fraction": round(water_fraction, 3),
        "tide_only": True,
    }
    write(px, meta)
    print("wrote %s  %dx%d  water %.1f%%  max %.2f m/s (%.1f kn)"
          % (OUT_PNG, WIDTH, HEIGHT, 100 * water_fraction,
             meta["speed_max"], meta["speed_max"] * 1.94384))
    return 0


if __name__ == "__main__":
    sys.exit(main())
