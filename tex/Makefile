# Tasks tied to the LaTeX tree. Run from anywhere: make -C tex <target>.
PY ?= python3
LANGS = en es ca

# Python used to run code/generate_output.py (raw sockets need root or CAP_NET_RAW; the Docker image
# sets CODE_PY=python).
CODE_PY ?= sudo python

.PHONY: pdf $(foreach l,$(LANGS),pdf-$(l)) pages code_output swimlane

# PDFs and offline zips only (no site), all editions or one.
pdf:
	uab-xoi build --no-site

$(foreach l,$(LANGS),pdf-$(l)):
	uab-xoi build --no-site --langs $(subst pdf-,,$@)

# Every mission must fit one printed page in each built PDF.
pages:
	uab-xoi pages

# Re-runs code/snippets/*.py to refresh the committed .py.out files.
code_output:
	cd code && $(CODE_PY) ./generate_output.py

# Regenerates the .eps sequence diagrams from the .msc sources (mscgen).
swimlane:
	./common/fig/chapters/generate_swimlane.sh
