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
MAX_LINES = 120


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
                # WORD COORDINATES - the text layout cannot be parsed reliably.
                # The Bureau prints three months side by side, two day-columns
                # each, and entries go missing where a day has fewer turns:
                #   "1904 2210 3.88 ... 2102 1927 2232 3.37 ..."
                # That lone 2102 is a slack with no maximum after it. Reading
                # left to right cannot tell which of the six columns any entry
                # belongs to. The x position can.
                if pno == 2:
                    try:
                        words = page.extract_words()
                        report.append("")
                        report.append("=== PAGE 2 WORD POSITIONS (first 160) ===")
                        report.append("%8s %8s %8s  %s" % ("x0", "x1", "top", "text"))
                        for w in words[:160]:
                            report.append("%8.1f %8.1f %8.1f  %s"
                                          % (w["x0"], w["x1"], w["top"], w["text"]))
                        xs = sorted(round(w["x0"]) for w in words)
                        report.append("")
                        report.append("distinct x0 values: %d" % len(set(xs)))
                        report.append("x0 histogram (value:count), sorted:")
                        from collections import Counter
                        for x, n in sorted(Counter(xs).items()):
                            report.append("   %6d : %d" % (x, n))
                    except Exception as e:
                        report.append("extract_words failed: %s" % e)

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
