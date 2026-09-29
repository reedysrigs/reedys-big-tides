#!/usr/bin/env python3
"""
One-off: can we get FES2014 currents over OPeNDAP instead of FTP?

The FTP route spent three hours on a single archive without finishing.
AVISO's own email lists "FTP, Opendap or Data Extraction" as access methods,
and their THREDDS catalog contains fes2014a_currents. OPeNDAP subsets on the
SERVER, so instead of pulling a multi-GB global archive we would ask only for
the Australian box - a fraction of a percent of the data.

This writes what it finds to docs/_aviso_opendap.txt. Delete once the answer
is known.
"""
import os, sys, time, json
import requests
from requests.auth import HTTPBasicAuth

TDS = "https://tds-odatis.aviso.altimetry.fr/thredds"
CAT = TDS + "/catalog/dataset-auxiliary-fes-tide-model/fes2014a_currents"
OUT = "docs/_aviso_opendap.txt"

# The Australian box we actually need
WEST, EAST, SOUTH, NORTH = 108.0, 162.88, -48.0, -8.0

R = []
def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    R.append(line)


def get(url, auth, **kw):
    t0 = time.time()
    try:
        r = requests.get(url, auth=auth, timeout=90, **kw)
        return r, time.time() - t0
    except Exception as e:
        say("  EXCEPTION %s" % e)
        return None, time.time() - t0


def main():
    u = os.environ.get("AVISO_USER", "").strip()
    p = os.environ.get("AVISO_PASS", "").strip()
    if not u or not p:
        say("AVISO_USER / AVISO_PASS not set")
        return 1
    auth = HTTPBasicAuth(u, p)
    say("user %s (password %d chars)" % (u, len(p)))
    say("")

    # 1. the catalog, as XML - tells us the real file names
    for cat in (CAT + "/catalog.xml", CAT + "/catalog.html"):
        say("=== %s ===" % cat)
        r, dt = get(cat, auth)
        if r is None:
            continue
        say("  status %s  %.1fs  %d bytes  %s"
            % (r.status_code, dt, len(r.content), r.headers.get("content-type")))
        if r.status_code == 200:
            body = r.text
            say("  --- first 3000 chars ---")
            for line in body[:3000].split("\n"):
                say("  " + line.rstrip())
            break
        else:
            say("  --- first 400 chars ---")
            say("  " + r.text[:400].replace("\n", " "))
    say("")

    # 2. try an OPeNDAP .dds on a likely path, to see if the endpoint answers
    for guess in [
        "/dodsC/dataset-auxiliary-fes-tide-model/fes2014a_currents/eastward_velocity/m2.nc",
        "/dodsC/dataset-auxiliary-fes-tide-model/fes2014a_currents/m2.nc",
        "/dodsC/auxiliary/tide_model/fes2014a_currents/eastward_velocity/m2.nc",
    ]:
        url = TDS + guess + ".dds"
        say("=== %s ===" % url)
        r, dt = get(url, auth)
        if r is None:
            continue
        say("  status %s  %.1fs  %d bytes" % (r.status_code, dt, len(r.content)))
        say("  " + r.text[:600].replace("\n", " | "))
        if r.status_code == 200:
            say("")
            say("  *** OPeNDAP ANSWERS HERE - subsetting is possible ***")
            break
        say("")

    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(R) + "\n")
    say("")
    say("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
