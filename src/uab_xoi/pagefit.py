#!/usr/bin/env python3
"""Check that every mission fits on ONE printed page in each PDF edition.

Missions are meant to be handed out as single sheets; Spanish and Catalan run
longer than English, so a translated mission can spill onto a second page.
Reads each PDF's table of contents (page numbers of "11.N Mission ..." and of
the entry that follows the last mission) - no LaTeX run needed.

  pagefit.py                 check build/xoi-uab-study-guide-{en,es,ca}.pdf, exit 1 if any mission spills
  pagefit.py --lang es       only one language
  pagefit.py --lines         also print how many text lines spill onto the extra page
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from .paths import BASENAME, BUILD, LANGS, TEX
MISSION_CHAPTER = "11"  # "Missions" is chapter 11 of the book (Part III)


def pdftext(pdf, first, last=None):
    return subprocess.run(["pdftotext", "-layout", "-f", str(first), "-l", str(last or first), str(pdf), "-"],
                          capture_output=True, text=True).stdout


def toc_entries(pdf):
    """[(number or '', title, page)] in book order, from the first pages that hold the contents."""
    text = pdftext(pdf, 3, 8)
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*((?:\d+(?:\.\d+)*)?)\s*(\S.*?)\s*\.{0,}\s+(\d{1,3})\s*$", line)
        if m and not re.search(r"\d\s*/\s*\d", line):
            out.append((m.group(1), m.group(2), int(m.group(3))))
    return out


def index_page(pdf, lang, after):
    """First page after `after` that starts the Index of Concepts (whatever the last mission is followed by)."""
    m = re.search(r"\\strIndexTitle \{(.*?)\}", (TEX / lang / "strings.tex").read_text(encoding="utf-8"))
    title = m.group(1) if m else "Index"
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
    for page in range(after + 1, n + 1):
        if title.lower() in pdftext(pdf, page).lower():
            return page
    return None


def mission_spans(pdf, lang):
    """{'11.1': (first_page, pages_used)} for every mission."""
    entries = toc_entries(pdf)
    spans = {}
    for i, (num, _title, page) in enumerate(entries):
        if re.fullmatch(rf"{MISSION_CHAPTER}\.\d+", num) and num not in spans:
            nxt = next((p for n, _t, p in entries[i + 1:] if p > page), None) or index_page(pdf, lang, page)
            spans[num] = (page, (nxt - page) if nxt else None)
    return spans


def spill_lines(pdf, page):
    """Text lines on the page after `page`, excluding running headers/footers."""
    lines = [x for x in pdftext(pdf, page + 1).splitlines() if x.strip()
             and not re.search(r"\d+\s*/\s*\d+\s*$", x) and "Guide" not in x and "Guía" not in x and "Guia" not in x]
    return len(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=LANGS)
    ap.add_argument("--lines", action="store_true")
    args = ap.parse_args()
    bad = 0
    for lang in ([args.lang] if args.lang else LANGS):
        pdf = BUILD / f"{BASENAME}-{lang}.pdf"
        if not pdf.exists():
            print(f"{lang}: {pdf.name} not built, skipped")
            continue
        spans = mission_spans(pdf, lang)
        cells, spilled = [], []
        for num in sorted(spans, key=lambda k: int(k.split(".")[1])):
            page, used = spans[num]
            if used is None or used > 1:
                spilled.append(num)
                extra = f" (+{spill_lines(pdf, page)} lines)" if args.lines and used else ""
                cells.append(f"{num}:{used}p{extra}")
            else:
                cells.append(f"{num}:1p")
        bad += len(spilled)
        print(f"{lang}: " + " ".join(cells) + ("   <-- spills: " + ", ".join(spilled) if spilled else "   ok"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
