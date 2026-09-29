#!/usr/bin/env bash
# Pull FES2014 tidal-CURRENT constituents for the eight principal harmonics
# into fes-data/fes2014/, the layout pyTMD expects.
#
# AVISO User Services, 29 Sep 2026:
#   "Once registered, you have access to ALL AVISO products available through
#    the service, including FES2014 tidal currents. No additional subscription
#    is required for this product."
#   FTP host: ftp-access.aviso.altimetry.fr
#   FES products under: /auxiliary/tide_model/
#
# This DISCOVERS the directory layout rather than assuming it, and prints what
# it found if anything is missing, so a wrong guess costs one run instead of
# a silent empty model directory.
set -uo pipefail

HOST="ftp-access.aviso.altimetry.fr"
ROOT="/auxiliary/tide_model"
: "${AVISO_USER:?AVISO_USER not set}"
: "${AVISO_PASS:?AVISO_PASS not set}"

CONSTITUENTS="m2 s2 n2 k2 k1 o1 p1 q1"

ftp_ls () {  # ftp_ls <remote-dir>
  lftp -u "$AVISO_USER","$AVISO_PASS" "$HOST" \
    -e "set ssl:verify-certificate no; set net:max-retries 2; cls -1 $1/; bye" 2>&1
}

echo "=== $ROOT ==="
TOP=$(ftp_ls "$ROOT")
echo "$TOP"

# find the currents directory, whatever they have called it
CURDIR=$(echo "$TOP" | tr -d '\r' | sed 's#/$##' | grep -i 'fes2014' | grep -i 'current' | head -1)
if [ -z "$CURDIR" ]; then
  CURDIR=$(echo "$TOP" | tr -d '\r' | sed 's#/$##' | grep -i 'fes2014' | head -1)
  echo "no directory matched fes2014+current; falling back to: ${CURDIR:-<none>}"
fi
if [ -z "$CURDIR" ]; then
  echo "::error::Nothing under $ROOT looks like FES2014. Listing is above."
  exit 1
fi
CUR="$ROOT/$(basename "$CURDIR")"
echo
echo "=== $CUR ==="
SUB=$(ftp_ls "$CUR")
echo "$SUB"

# eastward / northward component directories
EAST=$(echo "$SUB" | tr -d '\r' | sed 's#/$##' | grep -iE 'east|_u$|^u$' | head -1)
NORTH=$(echo "$SUB" | tr -d '\r' | sed 's#/$##' | grep -iE 'north|_v$|^v$' | head -1)
if [ -z "$EAST" ] || [ -z "$NORTH" ]; then
  echo "::error::Could not find eastward/northward component directories under $CUR."
  echo "The listing above shows what is actually there - adjust the script."
  exit 1
fi
echo
echo "components: east='$EAST'  north='$NORTH'"

mkdir -p fes-data/fes2014/eastward_velocity fes-data/fes2014/northward_velocity

fetch_one () {  # fetch_one <remote-subdir> <local-subdir>
  local rsub="$1" lsub="$2" c
  for c in $CONSTITUENTS; do
    for name in "${c}.nc" "${c}.nc.gz" "$(echo "$c" | tr a-z A-Z).nc"; do
      if lftp -u "$AVISO_USER","$AVISO_PASS" "$HOST" -e "
           set ssl:verify-certificate no;
           get $CUR/$rsub/$name -o fes-data/fes2014/$lsub/$name;
           bye" >/dev/null 2>&1 && [ -s "fes-data/fes2014/$lsub/$name" ]; then
        case "$name" in *.gz) gunzip -f "fes-data/fes2014/$lsub/$name";; esac
        echo "  got $lsub/$c"
        break
      fi
      rm -f "fes-data/fes2014/$lsub/$name"
    done
  done
}

echo
echo "downloading $CONSTITUENTS"
fetch_one "$(basename "$EAST")"  eastward_velocity
fetch_one "$(basename "$NORTH")" northward_velocity

got=$(find fes-data/fes2014 -name '*.nc' | wc -l)
echo
echo "downloaded $got constituent files"
find fes-data/fes2014 -name '*.nc' -printf '  %p  %s bytes\n' | sort
if [ "$got" -lt 16 ]; then
  echo "::error::expected 16 files (8 constituents x 2 components), got $got."
  echo "Listings above show the real remote layout."
  exit 1
fi
