#!/usr/bin/env python3
"""
One-off: fetch the Bureau's own tidal stream table for The Rip and write
what it actually looks like to docs/_bom_rip_sample.txt.

The Bureau publishes IDO59002_2026_VIC_TS001.pdf - real slack water times and
stream rates for The Rip. That is strictly better than modelling them from
tide heights, so the model in bake_tidal_streams.py should be replaced by a
parse of this. This probe exists so the parser is written against the real
layout instead of a guess at it.

Delete this script and its workflow once the parser is in.
"""
import io, os, re, sys
import requests

URL = "https://www.bom.gov.au/ntc/IDO59002/IDO59002_2026_VIC_TS001.pdf"
OUT = "docs/_bom_rip_sample.txt"
MAX_LINES = 320


def main():
    try:
        r = requests.get(URL, timeout=60, headers={"User-Agent": "reedysrigs-tides/1.0"})
        r.raise_for_status()
    except Exception as e:
        print("FETCH FAILED: %s" % e, file=sys.stderr)
        return 1

    raw = r.content
    report = []
    report.append("url            %s" % URL)
    report.append("http status    %s" % r.status_code)
    report.append("content-type   %s" % r.headers.get("content-type"))
    report.append("bytes          %d" % len(raw))
    report.append("looks like pdf %s" % (raw[:4] == b"%PDF"))
    report.append("")

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            report.append("pages          %d" % len(pdf.pages))
            report.append("")
            shown = 0
            for pno, page in enumerate(pdf.pages, 1):
                if shown >= MAX_LINES:
                    break
                report.append("----- PAGE %d -----" % pno)
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    if shown >= MAX_LINES:
                        break
                    report.append("%3d| %s" % (shown, line))
                    shown += 1
                # tables, if the layout is tabular rather than text
                if pno == 1:
                    try:
                        tabs = page.extract_tables()
                        report.append("")
                        report.append("page 1 tables found: %d" % len(tabs))
                        for ti, t in enumerate(tabs[:2]):
                            report.append("  table %d: %d rows" % (ti, len(t)))
                            for row in t[:8]:
                                report.append("    %r" % (row,))
                    except Exception as e:
                        report.append("extract_tables failed: %s" % e)
    except Exception as e:
        report.append("pdfplumber failed: %s" % e)

    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(report) + "\n")
    print("wrote %s (%d lines)" % (OUT, len(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
