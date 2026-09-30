#!/usr/bin/env bash
# Pull FES2014 tidal-CURRENT constituents into fes-data/fes2014/.
#
# HISTORY, so nobody repeats it:
#   FTP (ftp-access.aviso.altimetry.fr) via lftp sat on a single 2.21 GB
#   archive for over an hour without finishing, with no network timeout, so a
#   dropped connection hung forever. Parallel FTP segments did not help either.
#
# The THREDDS catalog gives exact sizes and an HTTPS endpoint:
#   https://tds-odatis.aviso.altimetry.fr/thredds/fileServer/
#     dataset-auxiliary-fes-tide-model/fes2014a_currents/eastward_velocity.tar.xz
#   eastward  2.210 GB
#   northward 2.215 GB
#
# HTTPS supports range requests, so this fetches with aria2c across 16
# connections. Falls back to curl with resume if aria2c is unavailable.
#
# OPeNDAP is NOT offered for this dataset - the catalog publishes only
# HTTPServer, and every dodsC path 404s. Server-side subsetting is not an
# option; the whole archive has to come down once.
set -uo pipefail

BASE="https://tds-odatis.aviso.altimetry.fr/thredds/fileServer/dataset-auxiliary-fes-tide-model/fes2014a_currents"
: "${AVISO_USER:?AVISO_USER not set}"
: "${AVISO_PASS:?AVISO_PASS not set}"

# pyTMD requires every constituent its FES2014 definition lists - it will
# go looking for all 34 and fail on the first one missing. They are all in
# the archive we already download, so extracting the lot costs nothing but
# disk, and the full set is more accurate than the eight principal ones.
CONSTITUENTS="2n2 eps2 j1 k1 k2 l2 la2 m2 m3 m4 m6 m8 mf mks2 mm mn4 ms4 msf msqm mtm mu2 n2 n4 nu2 o1 p1 q1 r2 s1 s2 s4 sa ssa t2"
mkdir -p fes-data/fes2014/eastward_velocity fes-data/fes2014/northward_velocity

have_aria2 () { command -v aria2c >/dev/null 2>&1; }

fetch_http () {          # fetch_http <url> <outfile>
  local url="$1" out="$2"
  if have_aria2; then
    aria2c -x16 -s16 -k 32M --retry-wait=5 --max-tries=4 \
           --timeout=60 --connect-timeout=30 \
           --http-user="$AVISO_USER" --http-passwd="$AVISO_PASS" \
           --summary-interval=15 --console-log-level=warn \
           -o "$out" -d . "$url" && return 0
    echo "aria2c failed, trying curl"
  fi
  curl -fL --retry 4 --retry-delay 5 --connect-timeout 30 \
       --speed-limit 10240 --speed-time 120 \
       -u "$AVISO_USER:$AVISO_PASS" -C - -o "$out" "$url"
}

do_component () {        # do_component <base-name> <local-subdir>
  local base="$1"
  local sub="$2"
  # NOT on one line with base: under set -u bash expands every assignment
  # word before local creates any of them, so ${base} would be unbound.
  local tarball="${base}.tar.xz"
  echo
  echo "=== $tarball ==="
  df -h . | tail -1

  local t0=$SECONDS
  fetch_http "$BASE/$tarball" "$tarball" || { echo "::error::download failed: $tarball"; return 1; }
  local dt=$(( SECONDS - t0 )) sz
  sz=$(stat -c%s "$tarball")
  echo "downloaded $(( sz / 1048576 )) MB in ${dt}s  ($(( sz / 1048576 / (dt>0?dt:1) )) MB/s)"

  # published checksum, if it is there
  if curl -fsL -u "$AVISO_USER:$AVISO_PASS" -o "${tarball}.sha256sum" \
       "$BASE/${tarball}.sha256sum" 2>/dev/null && [ -s "${tarball}.sha256sum" ]; then
    local want have
    want=$(awk '{print $1}' "${tarball}.sha256sum" | head -1)
    have=$(sha256sum "$tarball" | awk '{print $1}')
    if [ "$want" = "$have" ]; then
      echo "sha256 OK"
    else
      echo "::error::sha256 mismatch for $tarball"
      echo "  published $want"
      echo "  got       $have"
      return 1
    fi
  else
    echo "no checksum published, continuing"
  fi

  # one decompression pass; -v gives the member listing for free
  local pats=()
  for c in $CONSTITUENTS; do
    pats+=( "--wildcards" "*${c}.nc" "--wildcards" "*$(echo "$c" | tr a-z A-Z).nc" )
  done
  echo "--- extracting ---"
  tar -xJvf "$tarball" --no-anchored --wildcards-match-slash "${pats[@]}" 2>&1 | head -40 \
    || echo "selective extract returned non-zero, checking what landed"

  find . -path ./fes-data -prune -o -name '*.nc' -print 2>/dev/null | while read -r f; do
    b=$(basename "$f" | tr 'A-Z' 'a-z')
    for c in $CONSTITUENTS; do
      if [ "$b" = "${c}.nc" ]; then
        mv -f "$f" "fes-data/fes2014/$sub/${c}.nc"
        echo "  placed $sub/${c}.nc  ($(stat -c%s "fes-data/fes2014/$sub/${c}.nc") bytes)"
      fi
    done
  done

  rm -f "$tarball" "${tarball}.sha256sum"
  find . -maxdepth 2 -type d -empty -not -path './.git*' -not -path './fes-data*' -delete 2>/dev/null
}

do_component eastward_velocity  eastward_velocity  || exit 1
do_component northward_velocity northward_velocity || exit 1

got=$(find fes-data/fes2014 -name '*.nc' | wc -l)
echo
echo "have $got constituent files"
find fes-data/fes2014 -name '*.nc' -printf '  %p  %s bytes\n' | sort
[ "$got" -ge 16 ] || { echo "::error::expected 16, got $got"; exit 1; }
