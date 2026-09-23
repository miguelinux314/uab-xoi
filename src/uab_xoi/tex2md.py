#!/usr/bin/env python3
"""Convert the book's LaTeX sources into mkdocs-material markdown pages.

For each language: pre-process every chapter/mission .tex (render bytefield /
tikz / schedule blocks to SVG, rewrite constructs pandoc cannot parse, resolve
figures), run pandoc with filters/xoi.lua, and write one page per file
under <out>/<lang>/. Also copies the PDFs and code snippets into assets and
generates the concept index page.

Any LaTeX command or environment the pipeline does not know fails the build
(strict audit), so new constructs never vanish silently from the site.
"""
import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from . import render_tex_svg
from .paths import BASENAME, BUILD, COMMON, TEX, WEB

HERE = Path(__file__).resolve().parent
GRAPHICS_DIRS = [COMMON / "style", COMMON / "fig" / "chapters", COMMON / "fig" / "missions"]
GRAPHICS_EXTS = [".pdf", ".eps", ".png", ".jpg", ".jpeg", ".svg"]

# Paper width (cm) for the LaTeX paper sizes actually available to \geometry
# in this book; only the width matters here (figure sizing is width-driven).
PAPER_WIDTHS_CM = {"a4paper": 21.0, "a5paper": 14.8, "b5paper": 17.6, "letterpaper": 21.59}


def compute_text_width_cm():
    """The PDF's main text-column width (cm), derived from style/style.tex's
    \\geometry options. A figure included at \\linewidth/\\textwidth in the
    PDF is exactly this wide when printed; the site sizes such figures to
    match (scaled by any enclosing minipage/wrapfigure), instead of
    stretching them to the web column, which is usually much wider."""
    tex = (COMMON / "style" / "style.tex").read_text(encoding="utf-8")
    m = re.search(r"\\usepackage\[([^\]]*)\]\{geometry\}", tex)
    if not m:
        return 17.0
    opts = m.group(1)
    def cm(name, default):
        n = re.search(rf"{name}=([\d.]+)cm", opts)
        return float(n.group(1)) if n else default
    paper = next((w for name, w in PAPER_WIDTHS_CM.items() if name in opts), 21.0)
    return round(paper - cm("left", 2.0) - cm("right", 2.0), 2)


TEXT_WIDTH_CM = compute_text_width_cm()

# A figure sized to its literal real-world PDF cm (CSS's 96dpi/2.54cm
# reference) reads visibly smaller on a screen than the same cm width does
# on paper: web body text is set noticeably larger than a book's print body
# text, so "real size" figures look undersized next to it. This multiplier
# is a single, tunable calibration knob (not physically meaningful on its
# own) applied to every figure/diagram width computed from TEXT_WIDTH_CM or
# a source file's own page size, so that diagram text ends up close to the
# size of the surrounding site body text. Adjust and rebuild to recalibrate.
FIGURE_SCALE = 1.35


def scaled_cm(value_cm):
    return round(value_cm * FIGURE_SCALE, 2)


@functools.lru_cache(maxsize=None)
def figure_size_cm(src):
    """Real physical (width_cm, height_cm) of a figure file's own page/box,
    when determinable: a .pdf's page size (pdfinfo), or an .eps's own
    %%BoundingBox. This is what \\includegraphics{name} - no width/height
    option at all - renders at in the PDF (LaTeX does not auto-fit it to the
    surrounding text width), so the site sizes it the same way."""
    if src.suffix == ".pdf":
        return render_tex_svg.pdf_page_size_cm(src)
    if src.suffix == ".eps":
        m = re.search(r"%%BoundingBox:\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)",
                      src.read_text(errors="replace"))
        if m:
            x0, y0, x1, y1 = map(float, m.groups())
            return (round((x1 - x0) * render_tex_svg.PT_TO_CM, 2),
                    round((y1 - y0) * render_tex_svg.PT_TO_CM, 2))
    return None


def frac_of_linewidth(width_str):
    """0.5 for "0.5\\linewidth"/"0.5\\textwidth", 1.0 for a bare
    "\\linewidth", else None (not a \\linewidth-relative value)."""
    m = re.match(r"^\s*([\d.]*)\s*\\(?:line|text)width\s*$", width_str or "")
    if not m:
        return None
    return float(m.group(1)) if m.group(1) else 1.0
TEXTS = {
    "en": {"concepts_intro": "Every highlighted concept in the guide, with links to where it is used.",
           "concepts_by_section": "By section",
           "concepts_alphabetical": "Alphabetical"},
    "es": {"concepts_intro": "Todos los conceptos destacados en la guía, con enlaces a los lugares donde se usan.",
           "concepts_by_section": "Por sección",
           "concepts_alphabetical": "Orden alfabético"},
    "ca": {"concepts_intro": "Tots els conceptes destacats a la guia, amb enllaços als llocs on s'utilitzen.",
           "concepts_by_section": "Per secció",
           "concepts_alphabetical": "Ordre alfabètic"},
}
# Display name for each edition's PDF-download button (write_frontpage()) and
# language switcher (web/mkdocs.yml's own separate `name:` per language).
LANGUAGE_LABELS = {"en": "English", "es": "Castellano", "ca": "Català"}

# Commands the pipeline knows about (after pre-processing). Anything else in
# a chapter aborts the build with a list of offenders.
KNOWN_COMMANDS = set("""
chapter section subsection subsubsection paragraph label ref pageref hyperref
href url footnote includegraphics item begin end textbf textit emph underline
texttt textsc textsf textrm textsuperscript textsubscript textcircled small tiny
scriptsize footnotesize normalsize large Large LARGE huge Huge centering
color textcolor rowcolor cellcolor multicolumn multirow hline cline toprule
midrule bottomrule caption verb S P copyright LaTeX TeX ldots dots quad qquad
hfill vfill today checkmark textbackslash textasciitilde textbar textless
textgreater textquotedbl textendash textemdash mbox par newline linebreak
concept conceptRef node colored otherBase zero one compact pdfbreak secref readMore availableIn nseq nack
ie eg etc inlineCode textgreek input hyperlink hypertarget
subjectName subjectNumber subjectDegree subjectYear strStudyGuide strYearSuffix
strBy strIndexTitle strPartNetworks strPartInternet strPartMissions
linewidth textwidth paperwidth alph Alph arabic roman Roman texttrademark
textregistered
""".split())
KNOWN_ENVS = set("""
itemize enumerate description center flushleft flushright minipage wrapfigure
tabular remark exercise verbatim showcode showcodenooutput
comment figurerow captionedfigure
""".split())
STR_MACRO = r"\\newcommand \\(\w+) \{(.*)\}"


def find_braced(text, i):
    """text[i] == '{' -> index just past the matching '}'."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{" and (j == 0 or text[j - 1] != "\\"):
            depth += 1
        elif text[j] == "}" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError("unbalanced braces")


def unwrap_command(text, name, n_braced):
    """Replace \\name[opt]...{a}{b} by the content of its last braced argument."""
    out, pos = [], 0
    pattern = re.compile(r"\\" + name + r"(?![A-Za-z])")
    for m in pattern.finditer(text):
        if m.start() < pos:
            continue
        i, args = m.end(), []
        while len(args) < n_braced:
            while i < len(text) and text[i] in " \n":
                i += 1
            if i < len(text) and text[i] == "[":
                i = text.index("]", i) + 1
            elif i < len(text) and text[i] == "{":
                end = find_braced(text, i)
                args.append(text[i + 1:end - 1])
                i = end
            else:
                break
        if len(args) < n_braced:
            continue
        out.append(text[pos:m.start()])
        out.append("{" + args[-1] + "}")
        pos = i
    out.append(text[pos:])
    return "".join(out)


def replace_braced_command(text, name, func):
    """Replace \\name{arg} by func(arg) (brace-aware)."""
    out, pos = [], 0
    for m in re.finditer(r"\\" + name + r"(?![A-Za-z])\s*\{", text):
        if m.start() < pos:
            continue
        end = find_braced(text, m.end() - 1)
        out.append(text[pos:m.start()])
        out.append(func(text[m.end():end - 1]))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def drop_command(text, name, n_braced=1):
    return unwrap_command(text, name, n_braced) if n_braced == 0 else \
        replace_braced_command(text, name, lambda a: "")


# Simple math symbols occasionally used bare in a chapter/section title (e.g.
# \section{Analog $\leftrightarrow$ Digital}). Titles are shown as plain text
# in places MathJax never runs (the right-hand "Table of contents" panel, the
# nav, the browser tab), so these are rewritten to their Unicode character
# and unwrapped from $...$ before pandoc ever sees them - add to this dict
# if a new heading starts using another simple symbol.
HEADING_MATH_SYMBOLS = {
    r"\Leftrightarrow": "⇔", r"\leftrightarrow": "↔",
    r"\Rightarrow": "⇒", r"\rightarrow": "→",
    r"\Leftarrow": "⇐", r"\leftarrow": "←",
    r"\geq": "≥", r"\ge": "≥", r"\leq": "≤", r"\le": "≤",
    r"\neq": "≠", r"\approx": "≈",
}


def simplify_heading_math(title):
    """Replace known-simple $...$ math spans in a heading with plain Unicode
    text; leaves anything it doesn't recognize (e.g. a genuine equation)
    as real math, for MathJax to render on the page itself."""
    def repl(m):
        inner = m.group(1)
        simplified = inner
        for cmd, ch in HEADING_MATH_SYMBOLS.items():
            simplified = simplified.replace(cmd, ch)
        if simplified != inner and not re.search(r"\\[A-Za-z]", simplified):
            return simplified
        return m.group(0)
    return re.sub(r"\$([^$]*)\$", repl, title)


def transform_braced_command(text, name, func):
    """Apply func to the first braced argument of \\name{...} (name may
    include a literal \\*? for a starred form), keeping \\name{} itself."""
    out, pos = [], 0
    for m in re.finditer(r"\\(" + name + r")(?![A-Za-z])\s*\{", text):
        if m.start() < pos:
            continue
        end = find_braced(text, m.end() - 1)
        out.append(text[pos:m.start()])
        out.append("\\" + m.group(1) + "{" + func(text[m.end():end - 1]) + "}")
        pos = end
    out.append(text[pos:])
    return "".join(out)


@functools.lru_cache(maxsize=None)
def glossary_canonical_terms(lang):
    """key (lowercased) -> pinned canonical term text for this language, from the maintainer-only
    glossary (private/i18n/<lang>/glossary.yaml's `terms:`) if present - private/ is gitignored, so
    a public checkout without it just gets {} and canonical_terms() falls back to first-occurrence
    text everywhere, same as before. Used to prefer a curated base/dictionary-form word (glossary
    entries are written that way by convention) over whatever inflected form (plural, conjugated)
    happened to be used at the term's first occurrence in the running text."""
    path = TEX.parent / "private" / "i18n" / lang / "glossary.yaml"
    if not path.exists():
        return {}
    try:
        import yaml
        terms = yaml.safe_load(path.read_text(encoding="utf-8")).get("terms") or {}
    except Exception as e:
        print(f"warning: could not read {path}: {e}")
        return {}
    out = {}
    for key, entry in terms.items():
        if not isinstance(entry, dict):
            continue
        if lang in entry:
            out[key.lower()] = entry[lang]
        elif entry.get("keep_english"):
            out[key.lower()] = key
    return out


def detex_title(text):
    """Best-effort plain-text version of a heading, for use as the nav/tab/
    browser-tab title (frontmatter `title:`). The on-page `#` heading keeps
    the original text (MathJax renders it fine there); only the title needs
    this, since nav labels show raw text with no LaTeX/math rendering."""
    for _ in range(3):
        text = re.sub(r"\\(?:textbf|textit|texttt|emph|underline|textsc|textrm|textsf|"
                      r"mathrm|mathbf|mathit)\{([^{}]*)\}", r"\1", text)
    # \begin{envname}[opt]{arg} - the trailing {arg} covers e.g. array's column spec.
    text = re.sub(r"\\begin\{[^}]*\}(\[[^\]]*\])?(\{[^{}]*\})?", "", text)
    text = re.sub(r"\\end\{[^}]*\}", "", text)
    text = text.replace("\\\\", " ")
    text = re.sub(r"\\left\s*(\\[{}]|[{}()\[\].|])?", "", text)
    text = re.sub(r"\\right\s*(\\[{}]|[{}()\[\].|])?", "", text)
    # Pandoc's own markdown escaping of literal [ ] (xoi.lua's "[num]" section-number prefix) -
    # keep them, rather than let the next line's generic LaTeX-escape stripping delete them too.
    text = text.replace("\\[", "[").replace("\\]", "]")
    text = re.sub(r"\\[^A-Za-z]", "", text)       # spacing/delimiter escapes (\{, \,, \.)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)  # unrecognized commands: keep the word
    text = text.replace("$", "").replace("{", "").replace("}", "").replace("^", "")
    return re.sub(r"\s+", " ", text).strip()


def itemize_with_labels_to_description(text):
    out, stack, pos = [], [], 0
    for m in re.finditer(r"\\(begin|end)\{itemize\}", text):
        if m.group(1) == "begin":
            stack.append(m)
        else:
            start = stack.pop()
            body = text[start.end():m.start()]
            if re.search(r"\\item\s*\[", body) and not stack:
                out.append(text[pos:start.start()])
                # The term of a description item is rendered bold by pandoc already: a
                # \textbf inside it nests bold in bold and comes out as literal ****X**:**.
                body = re.sub(r"(\\item\s*\[)\s*\\textbf\{([^{}]*)\}([^\]]*\])", r"\1\2\3", body)
                out.append("\\begin{description}" + body + "\\end{description}")
                pos = m.end()
    out.append(text[pos:])
    return "".join(out)


LIST_MARKER = re.compile(r"^( *)((?:[-*+]|\d+[.)]))( +)(?=\S)")
FENCE = re.compile(r"^ *((`{3,})|(~{3,}))")


def normalize_list_indent(md):
    """Pandoc's gfm writer indents a nested list item by the width of its parent's
    marker (2 spaces under "- ", 3 under "1. "), but Python-Markdown (mkdocs) only nests
    on 4 spaces - with less, the sublist silently becomes a sibling. Re-indent every
    list level (and the paragraphs, fences and blocks inside list items) to 4 spaces per
    level; text outside lists, e.g. admonition/tab bodies, keeps its indentation."""
    out, stack, fence = [], [], None
    for line in md.split("\n"):
        if fence is not None:
            delta, chars = fence
            stripped = line.strip()
            out.append(_shift(line, delta))
            if stripped and set(stripped) == {chars[0]} and len(stripped) >= len(chars):
                fence = None
            continue
        if not line.strip():
            out.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = LIST_MARKER.match(line)
        if m:
            content = len(m.group(0))
            while stack and stack[-1][1] > indent:
                stack.pop()
            new_indent = stack[-1][2] + 4 if stack else indent
            stack.append((indent, content, new_indent))
            out.append(" " * new_indent + line[indent:])
            continue
        while stack and stack[-1][1] > indent:
            stack.pop()
        delta = 0
        if stack:
            _orig_marker, orig_content, new_marker = stack[-1]
            delta = new_marker + 4 + (indent - orig_content) - indent
        f = FENCE.match(line)
        if f:
            fence = (delta, f.group(1))
        out.append(_shift(line, delta))
    return "\n".join(out)


def _shift(line, delta):
    if delta >= 0:
        return " " * delta + line if line.strip() else line
    lead = len(line) - len(line.lstrip(" "))
    return line[min(-delta, lead):]


DEFAULT_LANG = "en"  # published at the site root; others under their own /<lang>/ - web/mkdocs.yml

# The "Computer Networks"/"Internet" landing pages (networks.md/internet.md - see page_list()):
# roman numeral (matching the PDF's part-cover pages, which use the numeral graphically instead of
# spelling out "Part") and the section's own chapters (\label of each, in book order), so the
# landing page can list them - mirrors the PDF part-cover's own chapter-list preview.
PART_INFO = {
    "networks.md": ("I", ["sec:piercing", "sec:where", "sec:packets", "sec:stack_layers"]),
    "internet.md": ("II", ["sec:internet", "sec:layer2", "sec:layer3", "sec:layer4", "sec:layer7"]),
}


class Converter:
    def __init__(self, lang, out_dir, all_langs=("en", "es", "ca"), strict=True):
        self.lang = lang
        self.all_langs = list(all_langs)
        self.out = out_dir / lang
        self.assets = self.out / "assets"
        self.strict = strict
        self.srcdir = TEX / lang
        self.strings = dict(re.findall(STR_MACRO, (TEX / lang / "strings.tex")
                                       .read_text(encoding="utf-8")))
        self.pages = self.page_list()
        self.labels = self.label_map()
        self.problems = []
        self.concepts_path = BUILD / f"concepts_{lang}.jsonl"
        self.labels_path = BUILD / f"labels_{lang}.json"

    # -- page inventory -------------------------------------------------------
    def page_list(self):
        main = (TEX / "main.tex").read_text(encoding="utf-8")
        pages = []
        for rel in re.findall(r"\\input\{\\docLang/((?:chapters|missions)/[^}]+)\}", main):
            stem = Path(rel).stem
            if stem == "copyright":
                # Split into license.md/ai_usage.md by split_copyright(); the
                # frontpage itself (index.md) is hand-composed, not from a
                # source file - see write_frontpage().
                continue
            elif stem == "chapter_the_course":
                page = "course.md"
            elif stem == "part_networks":
                # Landing page for the "Computer Networks" nav section (web/mkdocs.yml): just the
                # part's own intro blurb (\input right after \part{...} in main.tex, also pulled
                # onto the PDF's part-cover page there via a negative \vspace at its own top) - kept
                # out of chapter_piercing_the_veil.tex so that chapter isn't mistaken for the part's
                # own landing page and doesn't carry content that belongs to the part, not it.
                page = "networks.md"
            elif stem == "part_internet":
                page = "internet.md"  # same idea, for the "Internet" nav section
            elif stem == "mission_index":
                page = "missions/index.md"
            elif stem.startswith("mission"):
                page = f"missions/{stem}.md"
            else:
                page = stem.removeprefix("chapter_") + ".md"
            pages.append((rel, page))
        return pages

    def label_map(self):
        """label -> {num, title, page} from the PDF .aux (numbers) + sources (pages)."""
        info = {}
        aux = TEX / f"main_{self.lang}.aux"
        if aux.exists():
            text = aux.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"\\newlabel\{([^}]*)\}\{", text):
                i, groups = m.end() - 1, []
                try:
                    inner_end = find_braced(text, i)
                    j = i + 1
                    while j < inner_end - 1 and len(groups) < 3:
                        if text[j] == "{":
                            e = find_braced(text, j)
                            groups.append(text[j + 1:e - 1])
                            j = e
                        else:
                            j += 1
                except ValueError:
                    continue
                if len(groups) >= 3:
                    info[m.group(1)] = {"num": groups[0], "title": groups[2]}
        else:
            print(f"warning: {aux.name} not found; section numbers will be missing "
                  f"from cross-references (run `make pdf-{self.lang}` first)")
        for rel, page in self.pages:
            for label in re.findall(r"\\label\{([^}]*)\}", (self.srcdir / rel).read_text(encoding="utf-8")):
                info.setdefault(label, {"num": "", "title": label})["page"] = page
        return {k: v for k, v in info.items() if "page" in v}

    # -- figures ----------------------------------------------------------------
    def resolve_graphic(self, name):
        for d in GRAPHICS_DIRS:
            for ext in [""] + GRAPHICS_EXTS:
                p = d / (name + ext)
                if p.is_file():
                    return p
        return None

    def web_figure(self, src):
        """Copy/convert a figure into assets/fig and return its web file name."""
        fig_dir = self.assets / "fig"
        fig_dir.mkdir(parents=True, exist_ok=True)
        if src.suffix in (".pdf", ".eps"):
            dst = fig_dir / (src.stem + ".svg")
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                pdf = src
                if src.suffix == ".eps":
                    pdf = BUILD / "rendered" / (src.stem + ".pdf")
                    pdf.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["epstopdf", str(src), "--outfile=" + str(pdf)], check=True)
                subprocess.run(["pdftocairo", "-svg", str(pdf), str(dst)], check=True)
        else:
            dst = fig_dir / src.name
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                shutil.copy(src, dst)
        return dst.name

    # \begin{minipage}[opt]{width}, \begin{wrapfigure}[opt]{pos}{width} (its
    # last brace is the width) and \includegraphics[opts]{name} (name
    # excludes an already-resolved site path), in document order.
    STRUCTURE_RE = re.compile(
        r"\\begin\{minipage\}(?:\[[^\]]*\])?\{(?P<mp_width>[^}]*)\}"
        r"|\\end\{minipage\}"
        r"|\\begin\{wrapfigure\}(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}"
        r"|\\end\{wrapfigure\}"
        r"|\\includegraphics(?P<ig_opts>\[[^\]]*\])?\{(?P<ig_name>(?!\.\./|assets/)[^}]*)\}")

    def sized_includegraphics(self, rel, opts, name, prefix, scale):
        """`scale` is the fraction of the PDF's real text width (see
        TEXT_WIDTH_CM) the current minipage nesting represents, or None
        inside a wrapfigure - real-size sizing doesn't apply there, it's
        handled entirely by web/css/xoi.css's .wrap instead."""
        src = self.resolve_graphic(name)
        if not src:
            self.problems.append(f"{rel}: figure not found: {name}")
            return ""
        href = prefix + "assets/fig/" + self.web_figure(src)
        opts = opts or ""
        if scale is None:
            abs_attr = re.findall(r"(?:width|height)=[^,\]]+", opts)
            return "\\includegraphics" + ("[" + ",".join(abs_attr) + "]" if abs_attr else "") + "{" + href + "}"
        width_opt = re.search(r"width=([^,\]]+)", opts)
        frac = frac_of_linewidth(width_opt.group(1)) if width_opt else None
        if frac is not None:
            width_cm = scaled_cm(frac * scale * TEXT_WIDTH_CM)
            return f"\\includegraphics[width={width_cm}cm]{{{href}}}"
        abs_attr = re.findall(r"(?:width|height)=[^,\]]+(?:cm|mm|in|pt|px)", opts)
        if abs_attr:
            return "\\includegraphics[" + ",".join(abs_attr) + "]{" + href + "}"
        # No size option at all: LaTeX renders this at the figure's own real
        # size (it does not auto-fit to \linewidth), so the site does too.
        size = figure_size_cm(src)
        if size:
            return f"\\includegraphics[width={scaled_cm(size[0])}cm]{{{href}}}"
        return "\\includegraphics{" + href + "}"

    def resolve_figures(self, rel, text, prefix):
        """Resolve every \\includegraphics path to its site asset, sized to
        match its real printed size (scaled by any enclosing minipage) -
        see sized_includegraphics() - except inside a wrapfigure."""
        out, pos = [], 0
        mp_scale, wrap_depth = [1.0], 0
        for m in self.STRUCTURE_RE.finditer(text):
            out.append(text[pos:m.start()])
            pos = m.end()
            head = m.group(0)
            if head.startswith("\\begin{minipage}"):
                frac = frac_of_linewidth(m.group("mp_width"))
                mp_scale.append(mp_scale[-1] * frac if frac is not None else mp_scale[-1])
            elif head.startswith("\\end{minipage}"):
                if len(mp_scale) > 1:
                    mp_scale.pop()
            elif head.startswith("\\begin{wrapfigure}"):
                wrap_depth += 1
            elif head.startswith("\\end{wrapfigure}"):
                wrap_depth = max(0, wrap_depth - 1)
            else:
                out.append(self.sized_includegraphics(
                    rel, m.group("ig_opts"), m.group("ig_name"), prefix,
                    None if wrap_depth else mp_scale[-1]))
                continue
            out.append(head)
        out.append(text[pos:])
        return "".join(out)

    # -- pre-processing -------------------------------------------------------
    @staticmethod
    def expand_captioned_images(text):
        """\\captionedimage{file}{caption}{width}{url}{height} -> a captionedfigure
        environment around a linked \\includegraphics (so figure resolution and
        sizing see a normal \\includegraphics), laid out by xoi.lua/xoi.css."""
        text = re.sub(
            r"\\petraqr\{([^}]*)\}\{([^}]*)\}",
            lambda m: "\\captionedimage{%s}{}{0}{%s}{5cm}" % (m.group(1), m.group(2)),
            text)
        out, pos = [], 0
        for m in re.finditer(r"\\captionedimage(?![A-Za-z])", text):
            if m.start() < pos:
                continue
            i, args = m.end(), []
            for _ in range(5):
                while text[i] in " \n":
                    i += 1
                end = find_braced(text, i)
                args.append(text[i + 1:end - 1])
                i = end
            name, caption, _width, url, height = args
            out.append(text[pos:m.start()])
            out.append("\\begin{captionedfigure}\\href{" + url + "}{\\includegraphics[height=" + height + "]{" + name
                       + "}}" + ("\\\\ " + caption if caption.strip() else "") + "\\end{captionedfigure}")
            pos = i
        out.append(text[pos:])
        return "".join(out)

    def preprocess(self, rel, text, page):
        text = self.expand_captioned_images(text)
        prefix = "../" * (page.count("/"))
        heroes = re.findall(r"\\chapterimage\{([^}]*)\}", text)
        text = re.sub(r"\\chapterimage\{[^}]*\}", "", text)
        hero = None
        if heroes:
            src = self.resolve_graphic(heroes[0])
            if src:
                hero = prefix + "assets/fig/" + self.web_figure(src)

        # Blocks rendered to SVG, sized to their real (standalone PDF) size -
        # independent of any enclosing minipage, since a bytefield/tikzpicture
        # isn't itself given a \linewidth-relative width in the source. Done
        # first, before any of the pandoc-oriented simplification below (in
        # particular the \raisebox/\rotatebox unwrapping a few lines down),
        # so the fragment handed to the real pdflatex-based renderer matches
        # the PDF exactly instead of losing rotation/vertical positioning.
        def render_block(m):
            try:
                svg, width_cm, _ = render_tex_svg.render(m.group(0), lang=self.lang)
            except render_tex_svg.RenderError as e:
                self.problems.append(f"{rel}: cannot render block to SVG: {e}")
                return ""
            rendered = self.assets / "rendered"
            rendered.mkdir(parents=True, exist_ok=True)
            shutil.copy(svg, rendered / svg.name)
            size_opt = f"[width={scaled_cm(width_cm)}cm]" if width_cm else ""
            return "\\includegraphics" + size_opt + "{" + prefix + "assets/rendered/" + svg.name + "}"
        for pattern in (r"\\CellHeight.*?\\end\{schedule\}",
                        r"\\begin\{bytefield\}.*?\\end\{bytefield\}",
                        r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}"):
            text = re.sub(pattern, render_block, text, flags=re.S)

        for name in ("chapter\\*?", "section\\*?", "subsection\\*?",
                    "subsubsection\\*?", "paragraph\\*?"):
            text = transform_braced_command(text, name, simplify_heading_math)

        text = re.sub(r"^\\ \\\\\[[^\]]*\]\s*$", "", text, flags=re.M)
        text = re.sub(r"\\begin\{multicols\}\{\d+\}|\\end\{multicols\}", "", text)  # two-column lists are PDF-only
        text = re.sub(r"\\(?:todo|thispagestyle|pagestyle)\{[^}]*\}", "", text)
        text = re.sub(r"\\(?:vspace|hspace)\*?\{[^}]*\}", "", text)
        text = re.sub(r"\\(?:newpage|clearpage|noindent|centering|raggedright|raggedleft|hfill|vfill|smallskip|"
                      r"medskip|bigskip|phantomsection|compact|pdfbreak|makeatletter|makeatother)(?![A-Za-z])", "", text)
        # \chapter{...} wrapped in a \makeatletter/\let/\makeatother block that
        # suppresses its table-of-contents entry (PDF-only; the site's nav is separate).
        text = re.sub(r"\\let\\[A-Za-z@]+\\[A-Za-z@]+\s*", "", text)
        text = re.sub(r"\\warning(?![A-Za-z])", "⚠", text)
        text = re.sub(r"\\url\{([^}/:]+)\}", r"\\texttt{\1}", text)

        for name, n in (("raisebox", 2), ("makebox", 1), ("mbox", 1), ("parbox", 2),
                        ("rotatebox", 2)):
            text = unwrap_command(text, name, n)
        text = replace_braced_command(text, "centerline",
                                      lambda a: "\\begin{center}" + a + "\\end{center}")

        # Figures: resolve paths and size them close to how big they print
        # (see resolve_figures()/TEXT_WIDTH_CM), instead of stretching every
        # figure to the full (often much wider) web column.
        text = self.resolve_figures(rel, text, prefix)

        # 2+ \includegraphics in a row (no blank line between them) flow side
        # by side in the PDF; wrap them so the site lays them out the same
        # way instead of stacking each one full-width (web/css/xoi.css
        # .figure-row).
        text = re.sub(r"(?:\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}[ \t]*\n?){2,}",
                      lambda m: "\\begin{figurerow}\n" + m.group(0) + "\\end{figurerow}\n", text)

        # 2+ adjacent minipages (chapter_layer{2,3,4,7}.tex's opening bytefield-stack +
        # network-diagram pair) sit side by side in the PDF via minipage's own layout;
        # the site's minipage handling (xoi.lua) just unwraps them, stacking each full-
        # width, so wrap the pair the same way as the plain-\includegraphics case above.
        text = re.sub(r"(?:\\begin\{minipage\}(?:\[[^\]]*\])?\{[^}]*\}.*?\\end\{minipage\}[ \t]*\n?){2,}",
                      lambda m: "\\begin{figurerow}\n" + m.group(0) + "\\end{figurerow}\n", text, flags=re.S)

        # Runs of \zero\one... become one monospace number
        text = re.sub(r"(?:\\(?:zero|one)(?![A-Za-z])\s*){2,}",
                      lambda m: "\\otherBase{" + re.sub(r"\\zero", "0", re.sub(r"\\one", "1", m.group(0)))
                      .replace(" ", "").replace("\n", "") + "}", text)

        # Code
        def inline_code(a):
            delim = next(d for d in "|!§¦#+" if d not in a)
            return "\\verb" + delim + a + delim
        text = replace_braced_command(text, "inlineCode", inline_code)
        text = replace_braced_command(
            text, "showCodeNoOutput",
            lambda p: "\\begin{showcodenooutput}\\hyperlink{codefile:%s}{%s}\\end{showcodenooutput}" % (p, p))
        text = replace_braced_command(
            text, "showCode",
            lambda p: "\\begin{showcode}\\hyperlink{codefile:%s}{%s}\\end{showcode}" % (p, p))

        text = re.sub(r"\\begin\{wrapfigure\}(\[[^\]]*\])?\{[^}]*\}\{[^}]*\}", r"\\begin{wrapfigure}", text)
        text = itemize_with_labels_to_description(text)
        return text, hero

    def audit(self, rel, text):
        """Fail on commands/environments the pipeline does not know."""
        scan = re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", "", text, flags=re.S)
        scan = re.sub(r"\\verb(.)(.*?)\1", "", scan)
        scan = re.sub(r"(?<!\\)%[^\n]*", "", scan)
        scan = scan.replace("\\\\", " ")
        scan = re.sub(r"\\\[.*?\\\]|\$\$.*?\$\$|(?<!\\)\$[^$]*\$|\\\(.*?\\\)", "", scan, flags=re.S)
        unknown = set()
        for m in re.finditer(r"\\([A-Za-z]+)\*?", scan):
            if m.group(1) not in KNOWN_COMMANDS:
                unknown.add("\\" + m.group(1))
        for m in re.finditer(r"\\begin\{([^}]*)\}", scan):
            if m.group(1) not in KNOWN_ENVS:
                unknown.add("environment " + m.group(1))
        for u in sorted(unknown):
            line = next((i + 1 for i, l in enumerate(text.splitlines())
                         if u.removeprefix("environment ") in l), "?")
            self.problems.append(f"{rel}:{line}: unsupported LaTeX construct {u} "
                                 f"(add a rule in src/uab_xoi/tex2md.py or src/uab_xoi/filters/xoi.lua)")

    # -- pandoc -----------------------------------------------------------------
    def pandoc(self, rel, text, page):
        prelude = ((TEX / self.lang / "strings.tex").read_text(encoding="utf-8")
                   + (HERE / "pandoc_prelude.tex").read_text(encoding="utf-8"))
        prelude = re.sub(r"\\PassOptionsToPackage\{[^}]*\}\{[^}]*\}", "", prelude)
        chapnum = ""
        m = re.search(r"\\chapter\{.*?\}\\label\{([^}]*)\}", text)
        if m and m.group(1) in self.labels:
            chapnum = self.labels[m.group(1)]["num"]
        env = dict(os.environ, XOI_LANG=self.lang, XOI_PAGE=page, XOI_CHAPNUM=chapnum,
                   XOI_ROOT=str(TEX), XOI_LABELS=str(self.labels_path),
                   XOI_CONCEPTS=str(self.concepts_path),
                   # +1: mkdocs clean URLs put every page (bar index.md) in its own directory
                   # ("layer3.md" -> ".../layer3/index.html"), one level deeper than "page" implies.
                   # Only matters here because xoi.lua's showcode() emits a raw <a download> (not a
                   # markdown link), which mkdocs does not auto-adjust the way it does for markdown
                   # image/link syntax (see finish_page()'s XOI_ASSETS, injected the same way).
                   XOI_ASSETS="../" * (page.count("/") + 1) + "assets/",
                   XOI_HEADER_SHIFT="")
        run = subprocess.run(
            ["pandoc", "-f", "latex", "-t", "gfm+attributes+tex_math_dollars", "--wrap=none",
             "-L", str(HERE / "filters" / "xoi.lua")],
            input=prelude + "\n" + text, capture_output=True, text=True, cwd=TEX, env=env)
        if run.returncode != 0:
            self.problems.append(f"{rel}: pandoc failed: {run.stderr.strip()}")
            return None
        if run.stderr.strip():
            print(run.stderr.strip())
        return normalize_list_indent(run.stdout)

    # -- pages ------------------------------------------------------------------
    def finish_page(self, md, page, hero):
        lines = md.splitlines()
        title = next((re.sub(r"\s*\{#[^}]*\}\s*$", "", l[2:]).strip()
                      for l in lines if l.startswith("# ")), Path(page).stem)
        title = detex_title(title)
        if hero:
            lines.insert(0, "![](" + hero + "){ .hero }\n")
        # Relative path back to THIS LANGUAGE's own assets/ folder. mkdocs's clean URLs put every
        # page (except index.md, handled separately in write_frontpage()) in its own directory -
        # "layer3.md" -> ".../layer3/index.html" - one level deeper than its "page" string implies,
        # and "missions/mission1.md" -> two. web/js/technical-terms.js reads this to fetch
        # assets/terms.json (the cross-language canonical term texts) without guessing the depth.
        relprefix = "../" * (page.count("/") + 1)
        lines.append(f'\n<script>window.XOI_ASSETS = "{relprefix}assets/";</script>')
        front = "---\ntitle: " + json.dumps(title) + "\n---\n\n"
        return front + "\n".join(lines) + "\n"

    def write_frontpage(self):
        """The actual landing page (index.md): hand-composed, not generated
        from a source file - see page_list()/split_copyright() for where the
        license/credits/course-logistics content it links to comes from."""
        title = f"{self.strings['strStudyGuide']}: {self.strings['subjectName']}"
        subtitle = detex_title(f"{self.strings['subjectNumber']} - {self.strings['subjectDegree']}"
                               f" - {self.strings['subjectYear']} {self.strings['strYearSuffix']}"
                               " - Universitat Autònoma de Barcelona")
        hero = None
        src = self.resolve_graphic("cover_background")
        if src:
            hero = "assets/fig/" + self.web_figure(src)
        parts = ["---", "title: " + json.dumps(title), "---", ""]
        if hero:
            parts += ["![](" + hero + "){ .hero }", ""]
        # Everything below the hero is centered, cover-page style (see
        # web/css/xoi.css .frontpage, which also tightens the H1's own
        # default bottom margin - Material's is quite large: 1.25em).
        # Subject name and its acronym in one bold title, then "Study Guide" and the course line.
        parts += ['<div class="frontpage" markdown="1">', "",
                  f"# **{detex_title(self.strings['subjectName'])} (XOI)**",
                  f'<p class="cover-studyguide">{self.strings["strStudyGuide"]}</p>',
                  # The academic year (e.g. "2026/27") is computed client-side, never baked in at
                  # build time, so it's always current no matter how stale the last build is -
                  # "current" meaning September of year X through August of X+1 both read "X/X+1".
                  '<p class="cover-year"><span id="xoi-academic-year"></span></p>',
                  f'<p class="cover-course">{subtitle}</p>',
                  # Not document$.subscribe (mkdocs-material's usual hook, see the other web/js/
                  # files): this inline script runs inline with the page body, before that
                  # bundle has necessarily loaded, but the span right above it is already parsed
                  # and in the DOM by the time a script tag after it runs, so a plain IIFE is
                  # enough - no need to wait for anything.
                  '<script>(() => {'
                  ' const el = document.getElementById("xoi-academic-year"); if (!el) return;'
                  ' const now = new Date();'
                  ' const startYear = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;'
                  ' el.textContent = `${startYear}/${String(startYear + 1).slice(-2)}`;'
                  '})();</script>', ""]
        # Order: downloads, then authorship (byline and logos) last (collected in two lists).
        downloads, byline = [], []
        # Every PDF edition, from any language's page. mkdocs-static-i18n
        # (docs_structure: folder) publishes the default locale (en) at the
        # site root and other locales (es, ca) under their own /<locale>/
        # subfolder (web/mkdocs.yml), so the relative path from here to each
        # *other* edition's PDF depends on both where this page is published
        # and where that edition is published - own_prefix gets back to the
        # site root (unless this already is the root), target_prefix then
        # steps into the target's own subfolder (unless it is the root/en).
        own_prefix = "" if self.lang == DEFAULT_LANG else "../"
        langs = sorted(self.all_langs, key=lambda l: LANGUAGE_LABELS.get(l, l).lower())

        def asset_href(lang, ext):
            name = f"{BASENAME}-{lang}.{ext}"
            if lang == self.lang:
                return "assets/" + name
            return own_prefix + ("" if lang == DEFAULT_LANG else f"{lang}/") + "assets/" + name

        for lang in langs:
            # Raw HTML, not a markdown link: mkdocs validates markdown links against the source tree,
            # where other locales' assets are not siblings of this page (the URLs below are right for
            # the published layout: en at the site root, es/ca in subfolders).
            downloads.append(f'<a class="md-button md-button--primary" href="{asset_href(lang, "zip")}">'
                             f":material-folder-zip: PDF {LANGUAGE_LABELS.get(lang, lang)}</a>")
        downloads.append("")
        # Author + department/university logos + CC license badge, matching
        # the PDF cover (chapters/cover.tex).
        logos = {name: self.resolve_graphic(name) for name in ("logo_uab", "logo_deic", "by-nc-sa")}
        logos = {name: self.web_figure(src) for name, src in logos.items() if src}
        byline += [
            '<p class="cover-byline">'
            f"<strong>{self.strings['strBy']}</strong> Miguel Hernández-Cabronero - "
            '<a href="mailto:miguel.hernandez@uab.cat">miguel.hernandez@uab.cat</a></p>',
            "",
        ]
        if logos:
            imgs = []
            if "logo_uab" in logos:
                imgs.append('<a href="https://uab.cat">'
                            f'<img src="assets/fig/{logos["logo_uab"]}" alt="UAB"></a>')
            if "logo_deic" in logos:
                imgs.append('<a href="https://deic.uab.cat">'
                            f'<img src="assets/fig/{logos["logo_deic"]}" alt="DEIC"></a>')
            if "by-nc-sa" in logos:
                imgs.append('<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">'
                           f'<img src="assets/fig/{logos["by-nc-sa"]}" alt="CC BY-NC-SA"></a>')
            byline += ['<p class="cover-logos">' + " ".join(imgs) + "</p>", ""]
        parts += downloads + byline + ["</div>", ""]
        (self.out / "index.md").write_text("\n".join(parts), encoding="utf-8")

    def split_copyright(self, by_page):
        """copyright.tex has two \\section*{...} (License and Credits, AI Usage,
        whatever their translated names) - split it into one page
        each instead of one page with ## sections."""
        rel = "chapters/copyright.tex"
        text = (self.srcdir / rel).read_text(encoding="utf-8")
        marks = [m.start() for m in re.finditer(r"\\section\*\{", text)]
        pages = ("license.md", "ai_usage.md")
        if len(marks) != len(pages):
            self.problems.append(f"{rel}: expected {len(pages)} \\section*{{...}} (License and Credits, "
                                 f"AI Usage) to split into {', '.join(pages)}, found {len(marks)}")
            return
        bounds = marks[1:] + [len(text)]
        starts = [0] + marks[1:]
        for page, start, end in zip(pages, starts, bounds):
            chunk, hero = self.preprocess(rel, text[start:end], page)
            self.audit(rel, chunk)
            md = self.pandoc(rel, chunk, page)
            if md is not None:
                by_page[page].append((md, hero))

    def wrap_wide_table(self, md):
        """Wrap the first GFM table found in a scrollable/draggable, full-
        viewport-width container (web/css/xoi.css .wide-table, site/js
        wide-tables.js) - for the missions coverage matrix, whose many
        columns don't fit the normal content column."""
        lines, out, i = md.splitlines(), [], 0
        while i < len(lines):
            if lines[i].lstrip().startswith("|"):
                start = i
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    i += 1
                table = "\n".join(lines[start:i])
                out += ['<div class="wide-table mission-table" markdown>', '<div class="wide-table-inner" markdown>',
                       "", table, "", "</div>", "</div>"]
            else:
                out.append(lines[i])
                i += 1
        return "\n".join(out)

    def concepts_page(self):
        by_key = defaultdict(list)
        first_seen_order = []
        if self.concepts_path.exists():
            for line in self.concepts_path.read_text(encoding="utf-8").splitlines():
                c = json.loads(line)
                if c["key"] not in by_key:
                    first_seen_order.append(c["key"])
                by_key[c["key"]].append(c)
        # The canonical term shown in the index below and, via main()'s combined assets/terms.json,
        # in the "Technical terms" nav list and its hover tooltip on every page
        # (web/js/technical-terms.js): the glossary's own pinned word when there is one (a curated
        # base/dictionary form, not inflected), else the first occurrence (book order) of the key -
        # which may itself be an inflected form (plural, conjugated), same as before.
        glossary = glossary_canonical_terms(self.lang)
        self.canonical_terms = {key: glossary.get(key.lower(), entries[0]["text"])
                                for key, entries in by_key.items()}
        title = self.strings["strIndexTitle"]
        # Excluded from search (search: exclude: true, read by Material's search plugin): it's just
        # a index of every term also findable on its own page, so it would otherwise flood results
        # with one hit per term for whatever the user typed.
        lines = ["---", "title: " + json.dumps(title), "search:", "  exclude: true", "---", "",
                 f"# {title}", "",
                 TEXTS[self.lang]["concepts_intro"], ""]

        # "By section": one column per top-level [N] chapter/section, terms in book order within
        # each. Chapter titles come from self.labels (any label whose num has no dot is a chapter).
        chapter_titles = {v["num"]: v["title"] for v in self.labels.values()
                          if v.get("num") and "." not in v["num"]}
        columns, column_order = defaultdict(list), []
        for key in first_seen_order:
            c = by_key[key][0]
            # A concept tagged before any heading on its page (e.g. a part's intro blurb, which has
            # no \section of its own) has no secnum/sectitle - bucket those under the page itself
            # instead of an unlabeled "[]" column.
            colkey = c["secnum"].split(".")[0] if c["secnum"] else c["page"]
            if colkey not in columns:
                column_order.append(colkey)
            columns[colkey].append(
                f'[{self.canonical_terms[key]}]({c["page"]}#{c["anchor"]}){{: data-key="{key}" }}')
        # <br>, not a literal newline: this is one row of a pipe table, where a bare newline
        # would end the row instead of just the cell's visible line.
        header = [f"{chapter_titles[n]}<br>[{n}]" if n in chapter_titles else n
                 for n in column_order]
        max_rows = max((len(v) for v in columns.values()), default=0)
        table = ["| " + " | ".join(header) + " |",
                 "| " + " | ".join(["---"] * len(header)) + " |"]
        for i in range(max_rows):
            row = [columns[n][i] if i < len(columns[n]) else "" for n in column_order]
            table.append("| " + " | ".join(row) + " |")
        lines.append(f"## {TEXTS[self.lang]['concepts_by_section']}")
        lines.append("")
        lines += ['<div class="wide-table tt-table" markdown>', '<div class="wide-table-inner" markdown>',
                  "", "\n".join(table), "", "</div>", "</div>", ""]

        # Alphabetical: same term list, this time flat and sorted, with a link to every distinct
        # place (page, section) where it's used.
        lines.append(f"## {TEXTS[self.lang]['concepts_alphabetical']}")
        lines.append("")
        for key in sorted(by_key, key=lambda k: self.canonical_terms[k].lower()):
            seen, links = set(), []
            for c in by_key[key]:
                sec = c["secnum"] or c["sectitle"]
                if (c["page"], sec) in seen:
                    continue
                seen.add((c["page"], sec))
                links.append(f"[§{sec}]({c['page']}#{c['anchor']})")
            lines.append(f'- **{self.canonical_terms[key]}**{{: data-key="{key}" }}: '
                        + ", ".join(links))
        # concepts.md doesn't go through finish_page() (it's written directly, not part of
        # self.pages), so it needs its own copy of the XOI_ASSETS script tag - see finish_page()'s
        # comment - for web/js/technical-terms.js's terms.json fetch (by-section/alphabetical
        # tooltips) to find the right path instead of 404ing.
        lines.append('\n<script>window.XOI_ASSETS = "../assets/";</script>')
        (self.out / "concepts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def copy_assets(self):
        self.assets.mkdir(parents=True, exist_ok=True)
        for ext in ("pdf", "zip"):
            f = BUILD / f"{BASENAME}-{self.lang}.{ext}"
            if f.exists():
                shutil.copy(f, self.assets / f.name)
            else:
                print(f"warning: {f.name} not found; the download link will be broken "
                      f"(run `uab-xoi build`)")
        code = self.assets / "code" / "snippets"
        code.mkdir(parents=True, exist_ok=True)
        for f in (TEX / "code" / "snippets").iterdir():
            if f.suffix in (".py", ".out"):
                shutil.copy(f, code / f.name)

    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        for stale in self.out.rglob("*.md"):
            stale.unlink(missing_ok=True)  # tolerate a concurrent run (make serve's watcher)
        self.labels_path.parent.mkdir(parents=True, exist_ok=True)
        self.labels_path.write_text(json.dumps(self.labels))
        if self.concepts_path.exists():
            self.concepts_path.unlink()
        by_page = defaultdict(list)
        for rel, page in self.pages:
            text = (self.srcdir / rel).read_text(encoding="utf-8")
            text, hero = self.preprocess(rel, text, page)
            self.audit(rel, text)
            md = self.pandoc(rel, text, page)
            if md is not None:
                if rel.endswith("mission_index.tex"):
                    md = self.wrap_wide_table(md)
                elif page in ("networks.md", "internet.md"):
                    # part_networks.tex/part_internet.tex are just the part's intro blurb, with no
                    # \chapter of their own (so no heading survives pandoc) - finish_page() needs an
                    # "# " line to title this landing page and to give web/mkdocs.yml's
                    # navigation.indexes something to show as the nav section's own label. The
                    # roman numeral matches the PDF's part-cover pages (shown there graphically,
                    # not as text); the chapter list below mirrors that same cover's own preview.
                    key = "strPartNetworks" if page == "networks.md" else "strPartInternet"
                    numeral, chapter_labels = PART_INFO[page]
                    title_line = f"# {self.strings['strPart']} {numeral}: {self.strings[key]}\n\n"
                    outline = "\n".join(
                        f"- [\\[{self.labels[label]['num']}\\] {self.labels[label]['title']}]"
                        f"({self.labels[label]['page']})"
                        for label in chapter_labels if label in self.labels)
                    md = title_line + md + "\n\n" + outline + "\n"
                elif page == "course.md":
                    # Site-only: show "About this course" (matches web/mkdocs.yml's nav label)
                    # instead of the PDF chapter's own numbered title ("[1] Intro: ..."); the PDF
                    # keeps that title unchanged. Keep the heading's anchor id so any existing link
                    # to #sec-course still resolves.
                    anchor = re.search(r"(\{#[^}]*\})\s*$", md.splitlines()[0])
                    lines = md.splitlines()
                    lines[0] = "# " + self.strings["strAboutCourse"] + (
                        (" " + anchor.group(1)) if anchor else "")
                    md = "\n".join(lines)
                by_page[page].append((md, hero))
        self.split_copyright(by_page)

        for page, parts in by_page.items():
            bodies = [md for md, _ in parts]
            hero = next((h for _, h in parts if h), None)
            out_md = self.finish_page(bodies[0], page, hero)
            dst = self.out / page
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(out_md, encoding="utf-8")
        self.write_frontpage()
        self.concepts_page()
        self.copy_assets()
        return self.problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", nargs="+", default=["en", "es", "ca"])
    ap.add_argument("--out", type=Path, default=BUILD / "site_src")
    ap.add_argument("--lenient", action="store_true",
                    help="report problems but exit 0")
    args = ap.parse_args()
    problems = []
    converters = {}
    for lang in args.langs:
        print(f"== {lang}")
        converters[lang] = Converter(lang, args.out, all_langs=args.langs)
        problems += converters[lang].run()

    # Combined cross-language term dictionary (key -> {lang: canonical text}), one identical copy
    # published into each language's own assets/ (mirrors copy_assets()'s per-language PDFs/zips).
    # Read by web/js/technical-terms.js for the "Technical terms" nav list (this page's own
    # language) and its hover tooltip (all built languages, however many are configured).
    terms = defaultdict(dict)
    for lang, conv in converters.items():
        for key, text in getattr(conv, "canonical_terms", {}).items():
            terms[key][lang] = text
    for lang, conv in converters.items():
        conv.assets.mkdir(parents=True, exist_ok=True)
        (conv.assets / "terms.json").write_text(
            json.dumps(terms, ensure_ascii=False), encoding="utf-8")

    # mkdocs resolves extra_css/extra_javascript relative to docs_dir, which
    # is this generated directory, not site/ (where they're authored) - copy
    # them in so they actually get served (they were silently 404ing).
    # "js" (unlike "css") is renamed to "scripts": mkdocs-static-i18n's
    # docs_structure="folder" mistakes a root-level folder named "js" for a
    # locale code and reroutes/drops its files - see web/mkdocs.yml.
    for kind, dst_name in (("css", "css"), ("js", "scripts"), ("img", "img")):
        src, dst = WEB / kind, args.out / dst_name
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)  # drop files removed from web/
            shutil.copytree(src, dst)

    for p in problems:
        print("ERROR: " + p)
    if problems and not args.lenient:
        sys.exit(f"{len(problems)} problem(s); fix them or rerun with --lenient")


if __name__ == "__main__":
    main()
