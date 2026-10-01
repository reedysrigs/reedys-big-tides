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

# We want every constituent the archive carries: the eight principal ones plus
# the shallow-water overtides (m4, ms4, mn4, m6 ...) that are exactly what makes
# the flow asymmetric in constricted water like The Rip and Western Port.
#
# So there is nothing to select, and selecting was actively harmful:
#   - "--wildcards *s2.nc" also matches eps2.nc and mks2.nc, so a later
#     "*ssa.nc" pattern then reports "Not found in archive" and tar exits
#     non-zero for no real reason.
#   - the output was piped to "head -40".  Once head closes the pipe tar takes
#     SIGPIPE and STOPS EXTRACTING.  Verified: the same command with head -20
#     extracts 20 of 34 files and still exits via the "|| echo" path, and the
#     old "got >= 16" check would have passed on a short set.
# Extracting the whole archive has neither problem and is simpler.
EXPECT_CONSTITUENTS=34
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

  # One decompression pass, whole archive, NO pipe on tar.  A pipe here can
  # SIGPIPE tar partway through extraction (see the note at the top); the log
  # goes to a file and we print a bounded tail of it instead.
  echo "--- extracting ---"
  local log="extract-${sub}.log"
  if tar -xJf "$tarball" >"$log" 2>&1; then
    echo "  extract OK"
  else
    echo "::error::extract failed for $tarball"
    tail -20 "$log" | sed 's/^/    /'
    rm -f "$log"
    return 1
  fi
  rm -f "$log"

  # Move into place under the lowercase constituent name.
  local placed=0 f b
  while IFS= read -r f; do
    b=$(basename "$f" | tr 'A-Z' 'a-z')
    mv -f "$f" "fes-data/fes2014/$sub/$b"
    placed=$(( placed + 1 ))
  done < <(find . -path ./fes-data -prune -o -name '*.nc' -print 2>/dev/null)
  echo "  placed $placed files into fes-data/fes2014/$sub"

  # The tarball is 2 GB and we are about to hold 4.5 GB of .nc; drop it now.
  rm -f "$tarball" "${tarball}.sha256sum"
  find . -maxdepth 2 -type d -empty -not -path './.git*' -not -path './fes-data*' -delete 2>/dev/null

  # Crop to the Australian box BEFORE anything caches these.  Each global file
  # is 132 MB (5761 x 2881 float32 amplitude + phase); 34 x 2 of them is 9.0 GB
  # against GitHub's 10 GB per-repo cache ceiling.  Cropping is verified
  # lossless inside the box - pyTMD returns bit-for-bit identical currents from
  # cropped files - and takes the set to a few hundred MB.
  echo "--- cropping $sub to the Australian box ---"
  if ! python3 scripts/crop_fes.py fes-data/fes2014/"$sub"/*.nc; then
    echo "::error::crop failed for $sub"
    return 1
  fi

  local n
  n=$(find "fes-data/fes2014/$sub" -name '*.nc' | wc -l)
  if [ "$n" -ne "$EXPECT_CONSTITUENTS" ]; then
    echo "::error::$sub has $n constituent files, expected $EXPECT_CONSTITUENTS"
    return 1
  fi
  echo "  $sub: $n constituents, $(du -sh "fes-data/fes2014/$sub" | cut -f1) after cropping"
}

do_component eastward_velocity  eastward_velocity  || exit 1
do_component northward_velocity northward_velocity || exit 1

got=$(find fes-data/fes2014 -name '*.nc' | wc -l)
want=$(( EXPECT_CONSTITUENTS * 2 ))
echo
echo "have $got constituent files, total $(du -sh fes-data | cut -f1)"
find fes-data/fes2014 -name '*.nc' -printf '  %p  %s bytes\n' | sort
[ "$got" -eq "$want" ] || { echo "::error::expected $want files, got $got"; exit 1; }
