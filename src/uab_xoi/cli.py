"""`uab-xoi`: build, serve and clean the study guide.

  uab-xoi build              PDFs + offline zips (build/xoi-uab-study-guide-<lang>.{pdf,zip}) + website (build/site)
  uab-xoi build --no-site    only the PDFs and zips
  uab-xoi serve              lean website (no PDFs, no zips), port 65535; --reload for live-reload
  uab-xoi clean              remove every generated file
  uab-xoi pages              check that every mission fits one printed page in each built PDF
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile

from . import pagefit
from .paths import BASENAME, BUILD, LANGS, ROOT, TEX, WEB

PDFLATEX = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-shell-escape"]
LATEX_JUNK = ("*.aux", "*.bbl", "*.bcf", "*.blg", "*.idx", "*.ilg", "*.ind", "*.lof", "*.log", "*.lot",
              "*.out", "*.ptc", "*.run.xml", "*.synctex.gz", "*.toc", "*.upa", "*.upb", "*.fls",
              "*.fdb_latexmk", "*-converted-to.pdf", "main_??.pdf", "main.pdf")


def sources_mtime():
    """Newest modification time among the files a PDF depends on."""
    newest = 0.0
    for path in TEX.rglob("*"):
        if path.is_file() and path.suffix in (".tex", ".py", ".out", ".png", ".jpg", ".pdf", ".eps") \
                and not path.name.startswith("main_") and "_minted" not in str(path):
            newest = max(newest, path.stat().st_mtime)
    return newest


def build_pdf(lang, force=False):
    out = BUILD / f"{BASENAME}-{lang}.pdf"
    if not force and out.exists() and out.stat().st_mtime >= sources_mtime() \
            and (TEX / f"main_{lang}.aux").exists():
        print(f"== {lang}: PDF up to date")
        return
    print(f"== {lang}: pdflatex")
    for _ in range(3):
        if subprocess.run(PDFLATEX + [f"main_{lang}.tex"], cwd=TEX, stdout=subprocess.DEVNULL).returncode:
            sys.exit(f"pdflatex failed for {lang}: see tex/main_{lang}.log")
    BUILD.mkdir(exist_ok=True)
    shutil.copy(TEX / f"main_{lang}.pdf", out)


def build_zip(lang):
    """The offline download: the PDF plus code/snippets (the PDF links to them relatively)."""
    top = f"{BASENAME}-{lang}"
    with zipfile.ZipFile(BUILD / f"{top}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(BUILD / f"{top}.pdf", f"{top}/{top}.pdf")
        for f in sorted((TEX / "code" / "snippets").iterdir()):
            if f.suffix in (".py", ".out"):
                z.write(f, f"{top}/code/snippets/{f.name}")
    print(f"== {lang}: {top}.zip")


def run_site_src(langs):
    from . import tex2md
    sys.argv = ["tex2md", "--langs", *langs, "--out", str(BUILD / "site_src")]
    tex2md.main()


def cmd_build(args):
    langs = args.langs or list(LANGS)
    for lang in langs:
        build_pdf(lang, args.force)
        build_zip(lang)
    if not args.no_site:
        run_site_src(langs)
        subprocess.run(["mkdocs", "build", "-f", str(WEB / "mkdocs.yml")], check=True)
        print(f"site: {BUILD / 'site'}")


def snapshot(paths, suffixes=(".tex", ".py", ".lua", ".css", ".js", ".svg", ".yml", ".html")):
    state = {}
    for base in paths:
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in suffixes and "_minted" not in str(f):
                state[f] = f.stat().st_mtime
    return state


def watch(langs, stop):
    """Regenerate the site sources when a source changes (polling: no extra dependency)."""
    paths = [TEX, WEB, ROOT / "src"]
    seen = snapshot(paths)
    while not stop.is_set():
        time.sleep(1)
        now = snapshot(paths)
        if now != seen:
            time.sleep(1)  # let a multi-file save settle
            seen = snapshot(paths)
            try:
                run_site_src(langs)
            except SystemExit as e:
                print(f"serve: {e}", file=sys.stderr)


def cmd_serve(args):
    langs = args.langs or list(LANGS)
    try:
        run_site_src(langs)
    except SystemExit as e:
        print(f"warning: site sources incomplete ({e})", file=sys.stderr)
    stop = threading.Event()
    mkdocs_cmd = ["mkdocs", "serve", "-f", str(WEB / "mkdocs.yml"), "-a", f"{args.host}:{args.port}"]
    if args.reload:
        threading.Thread(target=watch, args=(langs, stop), daemon=True).start()
    else:
        mkdocs_cmd.append("--no-livereload")
    try:
        subprocess.run(mkdocs_cmd)
    finally:
        stop.set()


def cmd_clean(args):
    for pattern in LATEX_JUNK:
        for f in TEX.rglob(pattern):
            f.unlink()
    for d in list(TEX.rglob("_minted*")) + [BUILD, *ROOT.glob("src/*.egg-info")]:
        shutil.rmtree(d, ignore_errors=True)
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    print("clean")


def cmd_pages(args):
    sys.argv = ["pagefit", "--lines"] + (["--lang", args.lang] if args.lang else [])
    pagefit.main()


def main():
    ap = argparse.ArgumentParser(prog="uab-xoi", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="PDFs, offline zips and website")
    p.add_argument("--langs", nargs="+", choices=LANGS)
    p.add_argument("--no-site", action="store_true", help="only PDFs and zips")
    p.add_argument("--force", action="store_true", help="recompile PDFs even if up to date")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("serve", help="website (no PDFs or zips)")
    p.add_argument("--host", default=os.environ.get("UAB_XOI_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("UAB_XOI_PORT", 65535)))
    p.add_argument("--langs", nargs="+", choices=LANGS)
    # Off by default: rebuilding+refreshing on every source save is disruptive while a bunch of
    # files are being edited in a row (e.g. by Claude Code). Opt in with --reload, or
    # UAB_XOI_RELOAD=1 (docker/Makefile's `serve` passes this through as an env var).
    p.add_argument("--reload", action=argparse.BooleanOptionalAction,
                   default=os.environ.get("UAB_XOI_RELOAD", "0") == "1",
                   help="regenerate the site and live-reload the browser on source changes")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("clean", help="remove generated files")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("pages", help="check each mission fits one page")
    p.add_argument("--lang", choices=LANGS)
    p.set_defaults(func=cmd_pages)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
