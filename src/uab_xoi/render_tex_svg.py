#!/usr/bin/env python3
"""Render a LaTeX fragment (bytefield, tikzpicture, schedule block) to SVG.

The fragment is compiled in a `standalone` document with the same colours,
fonts and packages as the book, then converted with dvisvgm (fallback:
pdftocairo). Results are cached by content hash under build/rendered/.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .paths import BUILD

CACHE_DIR = BUILD / "rendered"
PT_TO_CM = 2.54 / 72  # PDF/PostScript point ("bp"), as reported by pdfinfo

PREAMBLE = r"""\documentclass[11pt,border=6pt]{standalone}
% 11pt matches the book's own \documentclass[11pt,fleqn]{book} (main.tex) -
% standalone defaults to 10pt, which made diagram text visibly smaller than
% the book's own body text even at a "real size" width (src/uab_xoi/tex2md.py).
% border=6pt (not the usual 3pt): standalone's own auto-computed content box
% ran slightly short of the true glyph ascent for bytefield's tiny \bitheader
% digits, clipping their tops even at border=3pt - verified empirically (5pt
% was already enough, 6pt for margin) by comparing rendered PNGs at several
% border widths of the same fragment.
\usepackage[dvipsnames,table]{xcolor}
\definecolor{color1}{RGB}{243,102,25}
\definecolor{color2}{RGB}{0,100,140}
\definecolor{color3}{RGB}{40,100,35}
\definecolor{color4}{RGB}{243,102,25}
\usepackage[T1]{fontenc}
\usepackage{graphicx}
\usepackage{amsmath,amsfonts,amssymb}
\usepackage{bytefield}
\usepackage{tikz}
\usepackage{pgf-pie}
\usepackage{schedule}
\usepackage{circledsteps}
\usepackage{avant}
\usepackage{qrcode}
\renewcommand{\familydefault}{\sfdefault}
\newcommand{\otherBase}[1]{{\Large\color{color2}\texttt{#1}}}
\newcommand \zero {\otherBase{0}}
\newcommand \one {\otherBase{1}}
\newcommand \node[1]{\Circled[outer color=color1]{#1}}
\newcommand \nseq {\#seq}
\newcommand \nack {\#ack}
\newcommand \ie {\textit{i.e.}}
\newcommand \eg {\textit{e.g.}}
\newcommand \etc {\textit{etc.}}
"""

# The course schedule figure (chapter_the_course.tex) uses these as macros,
# not literal text, so it can be translated like the PDF - mirrors
# tex/<lang>/strings.tex, since this standalone doc doesn't \input it.
LANG_STRINGS = {
    "en": {"lecture": "Lecture", "full_class": "Full class",
           "problems": "Problems", "labs": "Labs",
           "control_tests": "Control tests",
           "lab_grade": "Lab grade", "final_max": "Max(Final exam; Final Retake)"},
    "es": {"lecture": "Teoría", "full_class": "\\mbox{Clase} \\mbox{completa}",
           "problems": "Problemas", "labs": "Prácticas",
           "control_tests": "Controles",
           "lab_grade": "Prácticas", "final_max": "Máx(Final; Recuperación)"},
    "ca": {"lecture": "Teoria", "full_class": "\\mbox{Classe} \\mbox{completa}",
           "problems": "Problemes", "labs": "Pràctiques",
           "control_tests": "Controls",
           "lab_grade": "Pràctiques", "final_max": "Màx(Final; Recuperació)"},
}

# schedule.sty hardcodes its day-of-week header text to English (\@M@week
# etc., used only for display - the \BeginOn{Monday}/\ifx day-matching logic
# is separate and untouched by this). Only the Monday-start list matters:
# \BeginOn{Monday} is the only one used in the book.
WEEKDAY_OVERRIDES = {
    "es": (r"\def\@M@week{{Lunes} {Martes} {Mi\'ercoles} {Jueves} {Viernes} "
           r"{S\'abado} {Domingo}}"),
    "ca": (r"\def\@M@week{{Dilluns} {Dimarts} {Dimecres} {Dijous} {Divendres} "
           r"{Dissabte} {Diumenge}}"),
}


def lang_preamble(lang):
    s = LANG_STRINGS.get(lang, LANG_STRINGS["en"])
    lines = [f"\\newcommand \\str{key.title().replace('_', '')} {{{val}}}"
             for key, val in s.items()]
    if lang in WEEKDAY_OVERRIDES:
        lines.append(r"\makeatletter" "\n" + WEEKDAY_OVERRIDES[lang] + "\n" + r"\makeatother")
    return "\n".join(lines) + "\n\\begin{document}\n"


class RenderError(Exception):
    pass


def pdf_page_size_cm(pdf_path):
    """(width_cm, height_cm) of a PDF's (first) page, via pdfinfo, or None."""
    run = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True)
    m = re.search(r"Page size:\s*([\d.]+) x ([\d.]+) pts", run.stdout)
    if not m:
        return None
    return (round(float(m.group(1)) * PT_TO_CM, 2), round(float(m.group(2)) * PT_TO_CM, 2))


def render(fragment, lang="en", cache_dir=CACHE_DIR):
    """Render `fragment` (a bytefield/tikzpicture/schedule block) to SVG,
    using a cached copy if unchanged. Returns (svg_path, width_cm, height_cm):
    the last two are the standalone PDF's own real physical page size (the
    `border=3pt` from the class counted in), i.e. how big this would print in
    the book - use them to size the figure on the site instead of stretching
    it to the (often much wider) web column. Either may be None if pdfinfo
    could not read the page size."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    preamble = PREAMBLE + lang_preamble(lang)
    digest = hashlib.sha256((preamble + fragment).encode("utf-8")).hexdigest()[:16]
    svg = cache_dir / f"{digest}.svg"
    meta = cache_dir / f"{digest}.json"
    if svg.exists() and meta.exists():
        size = json.loads(meta.read_text())
        return svg, size["width_cm"], size["height_cm"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "frag.tex").write_text(preamble + fragment + "\n\\end{document}\n",
                                      encoding="utf-8")
        run = subprocess.run(
            ["pdflatex", "-interaction=batchmode", "-halt-on-error",
             "-output-directory", str(tmp), "frag.tex"],
            cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pdf = tmp / "frag.pdf"
        if run.returncode != 0 or not pdf.exists():
            log = (tmp / "frag.log").read_text(errors="replace") if (tmp / "frag.log").exists() else ""
            errors = [l for l in log.splitlines() if l.startswith("!")]
            raise RenderError("pdflatex failed: " + ("; ".join(errors[:3]) or "no log"))
        width_cm, height_cm = pdf_page_size_cm(pdf) or (None, None)
        out = tmp / "frag.svg"
        if shutil.which("dvisvgm"):
            run = subprocess.run(
                ["dvisvgm", "--pdf", "--font-format=woff2", "--exact-bbox", "-o", str(out), str(pdf)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not out.exists():
            subprocess.run(["pdftocairo", "-svg", str(pdf), str(out)], check=True)
        shutil.copy(out, svg)
    meta.write_text(json.dumps({"width_cm": width_cm, "height_cm": height_cm}))
    return svg, width_cm, height_cm


if __name__ == "__main__":
    print(render(sys.stdin.read()))
