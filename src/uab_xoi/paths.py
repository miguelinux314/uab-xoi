"""Repository layout, in one place (the package is installed editable: `pip install -e .`)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "tex"            # LaTeX root: pdflatex always runs with this as cwd
COMMON = TEX / "common"       # language-independent: alias.tex, style/, fig/, shared chapters/
WEB = ROOT / "web"            # mkdocs config, css, js
BUILD = ROOT / "build"        # everything generated (gitignored, removed by `uab-xoi clean`)
LANGS = ("en", "es", "ca")
DEFAULT_LANG = "en"
BASENAME = "xoi-uab-study-guide"  # build/<BASENAME>-<lang>.{pdf,zip}
