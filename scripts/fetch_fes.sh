#!/usr/bin/env bash
# Pull FES2014 tidal-CURRENT constituents into fes-data/fes2014/, the layout
# pyTMD expects.
#
# Confirmed layout on ftp-access.aviso.altimetry.fr (29 Sep 2026):
#   /auxiliary/tide_model/fes2014a_currents/eastward_velocity.tar.xz
#   /auxiliary/tide_model/fes2014a_currents/northward_velocity.tar.xz
#   ... plus .sha256sum for each, and a readme.
#
# They are ARCHIVES, not directories. Each is downloaded, checksummed,
# and only the eight principal harmonics are extracted before it is deleted,
# so peak disk stays manageable on a runner.
set -uo pipefail

HOST="ftp-access.aviso.altimetry.fr"
DIR="/auxiliary/tide_model/fes2014a_currents"
: "${AVISO_USER:?AVISO_USER not set}"
: "${AVISO_PASS:?AVISO_PASS not set}"

CONSTITUENTS="m2 s2 n2 k2 k1 o1 p1 q1"

mkdir -p fes-data/fes2014/eastward_velocity fes-data/fes2014/northward_velocity

grab () {  # grab <remote-file> <local-file>
  lftp -u "$AVISO_USER","$AVISO_PASS" "$HOST" -e "
    set ssl:verify-certificate no;
    set net:max-retries 3;
    set xfer:clobber on;
    get $1 -o $2;
    bye"
}

do_component () {          # do_component <archive-base> <local-subdir>
  local base="$1" sub="$2"
  local tarball="${base}.tar.xz"

  echo
  echo "=== $tarball ==="
  grab "$DIR/$tarball" "$tarball" || { echo "::error::download failed: $tarball"; return 1; }
  ls -l "$tarball"

  # checksum, if they published one
  if grab "$DIR/${tarball}.sha256sum" "${tarball}.sha256sum" 2>/dev/null && [ -s "${tarball}.sha256sum" ]; then
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

  # ONE decompression pass. Listing and extracting separately meant xz ran
  # over the whole archive twice, which on a multi-GB file is minutes wasted.
  # -v prints each member as it is written, so the listing comes free.
  local pats=()
  for c in $CONSTITUENTS; do
    pats+=( "--wildcards" "*${c}.nc" "--wildcards" "*$(echo "$c" | tr a-z A-Z).nc" )
  done
  echo "--- extracting (members printed as they land) ---"
  tar -xJvf "$tarball" --no-anchored --wildcards-match-slash "${pats[@]}" 2>&1 | head -40 \
    || echo "selective extract returned non-zero, checking what landed"

  # flatten whatever directory structure came out
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
  # tidy any empty dirs the extract left behind
  find . -maxdepth 2 -type d -empty -not -path './.git*' -not -path './fes-data*' -delete 2>/dev/null
}

df -h . | tail -1
do_component eastward_velocity  eastward_velocity  || exit 1
df -h . | tail -1
do_component northward_velocity northward_velocity || exit 1
df -h . | tail -1

got=$(find fes-data/fes2014 -name '*.nc' | wc -l)
echo
echo "have $got constituent files"
find fes-data/fes2014 -name '*.nc' -printf '  %p  %s bytes\n' | sort
if [ "$got" -lt 16 ]; then
  echo "::error::expected 16 (8 harmonics x 2 components), got $got."
  echo "The archive listings above show the real member names."
  exit 1
fi
