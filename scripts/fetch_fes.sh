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

# The server stalls badly near the end of these transfers - one run logged 135
# consecutive samples at 0 B/s around 99%.  Sometimes it recovers (run 13 did,
# twice).  Sometimes aria2c gives up:
#
#   ERROR CUID#23 - Download aborted.  errorCode=2 Timeout.
#
# and that is where it got dangerous.  aria2c PREALLOCATES the output to the
# full size, so an aborted transfer leaves a file of exactly the right length
# with an unwritten hole in it.  The old curl fallback then ran "-C -",
# resumed from byte 2210806936 - already the end of the file - transferred 0
# bytes, and exited 0.  stat said 2108 MB, the same as a good download.  Only
# the sha256 check caught it:
#   published b3840ed0bbc49f88db0d682f4e07a7fe5537d62b9c1d1efdeeebba3fca45be16
#   got       917396c0d52cce790f0bddbb13a0bba0249e7375b1aa22ada2d34cb9bfb933a8
#
# So: retry aria2c as a whole process, which resumes correctly from its own
# .aria2 control file (it knows which segments are missing - a plain byte offset
# does not).  Only hand over to curl once that control file is gone, and delete
# the preallocated carcass first so curl starts from zero instead of "resuming"
# from the end of a file full of holes.
fetch_http () {          # fetch_http <url> <outfile>
  local url="$1" out="$2" attempt
  if have_aria2; then
    for attempt in 1 2 3; do
      if aria2c -x16 -s16 -k 32M --continue=true \
                --retry-wait=5 --max-tries=5 \
                --timeout=120 --connect-timeout=30 \
                --lowest-speed-limit=1K \
                --http-user="$AVISO_USER" --http-passwd="$AVISO_PASS" \
                --summary-interval=30 --console-log-level=warn \
                -o "$out" -d . "$url"; then
        return 0
      fi
      echo "aria2c attempt $attempt did not finish; resuming from its control file"
      sleep 10
    done
    echo "aria2c exhausted its attempts, starting clean with curl"
    # An aria2c partial is full-length with gaps, so resuming it is unsafe.
    rm -f "$out" "${out}.aria2"
  fi
  curl -fL --retry 4 --retry-delay 5 --connect-timeout 30 \
       --speed-limit 10240 --speed-time 300 \
       -u "$AVISO_USER:$AVISO_PASS" -o "$out" "$url"
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

  # Fetch the published checksum once, up front, so we can verify each try.
  local want=""
  if curl -fsL -u "$AVISO_USER:$AVISO_PASS" -o "${tarball}.sha256sum" \
       "$BASE/${tarball}.sha256sum" 2>/dev/null && [ -s "${tarball}.sha256sum" ]; then
    want=$(awk '{print $1}' "${tarball}.sha256sum" | head -1)
    echo "published sha256 $want"
  else
    echo "no checksum published - cannot verify this archive"
  fi

  # A corrupt download is a retryable condition, not a dead run.  A silent hole
  # in a 2 GB archive is the one failure mode that would otherwise reach the map
  # as plausible-looking wrong currents, so each try is verified and a bad one
  # is thrown away whole - no resuming into a file we already know is wrong.
  local try t0 dt sz have ok=0
  for try in 1 2 3; do
    t0=$SECONDS
    if ! fetch_http "$BASE/$tarball" "$tarball"; then
      echo "download attempt $try failed outright"
      rm -f "$tarball" "${tarball}.aria2"
      continue
    fi
    dt=$(( SECONDS - t0 ))
    sz=$(stat -c%s "$tarball")
    echo "attempt $try: $(( sz / 1048576 )) MB in ${dt}s  ($(( sz / 1048576 / (dt>0?dt:1) )) MB/s)"

    if [ -z "$want" ]; then
      echo "unverified, accepting it"
      ok=1; break
    fi
    have=$(sha256sum "$tarball" | awk '{print $1}')
    if [ "$want" = "$have" ]; then
      echo "sha256 OK"
      ok=1; break
    fi
    echo "sha256 MISMATCH on attempt $try - discarding and starting clean"
    echo "  published $want"
    echo "  got       $have"
    rm -f "$tarball" "${tarball}.aria2"
  done
  if [ "$ok" -ne 1 ]; then
    echo "::error::could not get a verified $tarball in 3 attempts"
    return 1
  fi

  # One decompression pass, whole archive, NO pipe on tar.  A pipe here can
  # SIGPIPE tar partway through extraction (see the note at the top); the log
  # goes to a file and we print a bounded tail of it instead.
  # Extract into a staging directory of its own.  The previous version swept the
  # whole working tree with "find . -name '*.nc'" and moved everything it found
  # into this component's folder - which in testing picked up 7 unrelated .nc
  # files and filed them as eastward constituents.  A clean repo never had any,
  # so it never bit, but it is not a property worth depending on.
  echo "--- extracting ---"
  local stage="stage-$sub" log="extract-${sub}.log"
  rm -rf "$stage"; mkdir -p "$stage"
  if tar -xJf "$tarball" -C "$stage" >"$log" 2>&1; then
    echo "  extract OK"
  else
    echo "::error::extract failed for $tarball"
    tail -20 "$log" | sed 's/^/    /'
    rm -f "$log"; rm -rf "$stage"
    return 1
  fi
  rm -f "$log"

  # Move into place under the lowercase constituent name.
  local placed=0 f b
  while IFS= read -r f; do
    b=$(basename "$f" | tr 'A-Z' 'a-z')
    mv -f "$f" "fes-data/fes2014/$sub/$b"
    placed=$(( placed + 1 ))
  done < <(find "$stage" -name '*.nc' -print 2>/dev/null)
  echo "  placed $placed files into fes-data/fes2014/$sub"

  # The tarball is 2 GB and we are about to hold 4.5 GB of .nc; drop it now.
  rm -f "$tarball" "${tarball}.sha256sum" "${tarball}.aria2"
  rm -rf "$stage"

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
