# UAB XOI - Study guide: Repository

![XOI Earth](https://github.com/miguelinux314/uab-xoi/raw/master/tex/common/fig/chapters/earth.jpg)

This repository contains the **study guide** for "Computer Networks and Internet"
(Xarxes d'Ordinadors i Internet), 104353 - Grau d'Enginyeria de Dades -- Universitat Autònoma de Barcelona.

Online:

* [English](https://miguelinux314.github.io/uab-xoi/)
* [Castellano](https://miguelinux314.github.io/uab-xoi/es/)
* [Català](https://miguelinux314.github.io/uab-xoi/ca/)

Offline (PDF + code snippets, unzip everything so the links to the code work):

* [Castellano](https://miguelinux314.github.io/uab-xoi/es/assets/xoi-uab-study-guide-es.zip) ·
  [Català](https://miguelinux314.github.io/uab-xoi/ca/assets/xoi-uab-study-guide-ca.zip) ·
  [English](https://miguelinux314.github.io/uab-xoi/assets/xoi-uab-study-guide-en.zip)

## Repository layout

| Path | What it is |
|---|---|
| `tex/` | The LaTeX sources; `pdflatex` always runs here. `tex/en/` is the original (English) text, `tex/es/` and `tex/ca/` the translated editions, `tex/common/` what is shared (style, macros, figures, cover, index), `tex/code/` the Python snippets embedded in the book |
| `web/` | The website: mkdocs-material configuration, CSS, JS |
| `src/uab_xoi/` | The `uab-xoi` Python package that renders the PDFs, offline zips and the website from `tex/` |
| `docker/` | The build/dev image (also used by CI) |
| `build/` | Everything generated (PDFs, zips, site); not tracked, removed by `make clean` |

## Building

Only Docker and `make` are needed:

```sh
make -C docker build   # once: build the image
make serve       # website at http://localhost:65535/uab-xoi/, live reload while you edit
make -C docker site    # PDFs, offline zips and the whole website into build/
make -C docker pdf     # only the PDFs and zips
```

Or on the host (TeX Live with `-shell-escape`, `pandoc`, `mscgen`, `dvisvgm`, poppler; see
`docker/requirements_apt.txt`):

```sh
pip install -e .    # provides the `uab-xoi` command
uab-xoi build    # build/xoi-uab-study-guide-<en|es|ca>.{pdf,zip} + build/site
uab-xoi serve    # lean live-reloading site (no PDFs or zips), port 65535
uab-xoi clean    # remove every generated file
```

Each edition can also be compiled on its own from `tex/`: `pdflatex -shell-escape main_en.tex` (or `main_es.tex`, `main_ca.tex`).

## Contributing

The English text under `tex/en/` is the maintained source; open issues or pull requests against it.
The Castellano and Català editions follow it.
