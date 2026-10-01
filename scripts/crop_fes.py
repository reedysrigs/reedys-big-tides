#!/usr/bin/env python3
"""
Crop a global FES2014 constituent file to the Australian box, in place.

Why this exists: each global FES2014 current constituent is 132 MB
(5761 x 2881 float32 amplitude + phase, uncompressed).  34 constituents x 2
components = 9.0 GB, against GitHub's 10 GB per-repo Actions cache ceiling.
Caching that would both crowd out every other cache in the repo and cost
minutes of upload on every run.

Cropping to the box the baker actually samples takes each file to roughly
4 MB, so the whole set caches in a few hundred MB.  This is verified lossless:
pyTMD returns bit-for-bit identical currents from cropped files as from global
ones, for every point inside the box.  See tests/test_crop_fes.py.

A margin is kept around the baker's grid so bilinear/spline interpolation at
the very edge still has neighbours on all sides.
"""
import sys
import pathlib
import numpy as np

# The baker's grid is 108.0..162.88 E, -48.0..-8.0 S.  Keep a margin so
# interpolation at the boundary is still interpolation, not extrapolation.
WEST, EAST = 108.0, 162.88
SOUTH, NORTH = -48.0, -8.0
MARGIN = 2.0

# A crop that keeps less than this many points in either direction means the
# longitude convention was not what we assumed, or the file is not FES.
MIN_POINTS = 200


def coord_names(ds):
    """Return (lat_name, lon_name) for a FES-style dataset."""
    lat = lon = None
    for cand in ("lat", "latitude", "LAT", "y"):
        if cand in ds.coords or cand in ds.dims:
            lat = cand
            break
    for cand in ("lon", "longitude", "LON", "x"):
        if cand in ds.coords or cand in ds.dims:
            lon = cand
            break
    if lat is None or lon is None:
        raise ValueError("no lat/lon coordinates found, have %r"
                         % (list(ds.coords),))
    return lat, lon


def crop_one(path, out_path=None):
    """Crop `path` to the AU box. Returns (kept_lat, kept_lon, in_bytes, out_bytes)."""
    import xarray as xr

    path = pathlib.Path(path)
    out_path = pathlib.Path(out_path) if out_path else path
    in_bytes = path.stat().st_size

    ds = xr.open_dataset(path, engine="netcdf4")
    try:
        latn, lonn = coord_names(ds)
        lat = np.asarray(ds[latn].values, dtype="float64")
        lon = np.asarray(ds[lonn].values, dtype="float64")

        # FES2014 publishes longitude 0..360.  Accept -180..180 as well rather
        # than assume: build a boolean mask in whichever convention the file
        # uses.  Australia does not straddle the seam in either convention, so
        # no wrap handling is needed - but check the result is sane below.
        lo, hi = WEST - MARGIN, EAST + MARGIN
        if lon.max() > 180.0:
            lon_mask = (lon >= lo) & (lon <= hi)
        else:
            lon_mask = (lon >= ((lo + 180.0) % 360.0) - 180.0) & \
                       (lon <= ((hi + 180.0) % 360.0) - 180.0)
        lat_mask = (lat >= SOUTH - MARGIN) & (lat <= NORTH + MARGIN)

        nlat, nlon = int(lat_mask.sum()), int(lon_mask.sum())
        if nlat < MIN_POINTS or nlon < MIN_POINTS:
            raise ValueError(
                "crop of %s kept only %d lat x %d lon points (need >=%d each); "
                "lat %.3f..%.3f lon %.3f..%.3f - longitude convention unexpected?"
                % (path.name, nlat, nlon, MIN_POINTS,
                   lat.min(), lat.max(), lon.min(), lon.max()))

        sel = ds.isel({latn: np.where(lat_mask)[0], lonn: np.where(lon_mask)[0]})

        # Compress: the globals are uncompressed float32, and zlib on a field
        # this smooth is worth roughly another 2x on top of the crop.
        enc = {v: {"zlib": True, "complevel": 4} for v in sel.data_vars}

        tmp = out_path.with_suffix(".nc.crop")
        sel.to_netcdf(tmp, format="NETCDF4", engine="netcdf4", encoding=enc)
        sel.close()
    finally:
        ds.close()

    tmp.replace(out_path)
    return nlat, nlon, in_bytes, out_path.stat().st_size


def main(argv):
    if len(argv) < 2:
        print("usage: crop_fes.py <file.nc> [file.nc ...]", file=sys.stderr)
        return 2
    total_in = total_out = 0
    for p in argv[1:]:
        try:
            nlat, nlon, bi, bo = crop_one(p)
        except Exception as exc:                     # noqa: BLE001
            print("::error::crop failed for %s: %s" % (p, exc), file=sys.stderr)
            return 1
        total_in += bi
        total_out += bo
        print("  cropped %-56s %4d x %4d  %6.1f MB -> %5.2f MB"
              % (p, nlat, nlon, bi / 1e6, bo / 1e6))
    if len(argv) > 2:
        print("  total %.2f GB -> %.2f GB  (%.1f%%)"
              % (total_in / 1e9, total_out / 1e9,
                 100.0 * total_out / max(total_in, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
