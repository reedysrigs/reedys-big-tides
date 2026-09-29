#!/usr/bin/env bash
# Pull the FES2014 tidal-CURRENT constituents for the eight principal
# harmonics into fes-data/fes2014/, which is the layout pyTMD expects.
#
# Only these eight are fetched. Together they carry the overwhelming
# majority of tidal current variance; the other 26 constituents in FES2014
# would multiply the download for very little on the water.
set -euo pipefail

HOST="ftp-access.aviso.altimetry.fr"
: "${AVISO_USER:?AVISO_USER not set}"
: "${AVISO_PASS:?AVISO_PASS not set}"

CONSTITUENTS="m2 s2 n2 k2 k1 o1 p1 q1"
REMOTE_ROOT="/auxiliary/tide_model/fes2014_currents"

mkdir -p fes-data/fes2014/eastward_velocity fes-data/fes2014/northward_velocity

# If the remote layout is not what we expect, print what IS there and stop,
# rather than silently producing an empty model directory.
listing=$(lftp -u "$AVISO_USER","$AVISO_PASS" "$HOST" -e "set ssl:verify-certificate no; cls -1 $REMOTE_ROOT/; bye" 2>&1 || true)
echo "remote $REMOTE_ROOT contains:"
echo "$listing"

for dir in eastward_velocity northward_velocity; do
  for c in $CONSTITUENTS; do
    lftp -u "$AVISO_USER","$AVISO_PASS" "$HOST" -e "
      set ssl:verify-certificate no;
      get $REMOTE_ROOT/$dir/${c}.nc -o fes-data/fes2014/$dir/${c}.nc;
      bye" || echo "could not fetch $dir/${c}.nc"
  done
done

got=$(find fes-data/fes2014 -name '*.nc' | wc -l)
echo "downloaded $got constituent files"
if [ "$got" -lt 16 ]; then
  echo "::error::expected 16 files (8 constituents x 2 components), got $got."
  echo "The listing above shows the real remote layout - adjust REMOTE_ROOT."
  exit 1
fi
