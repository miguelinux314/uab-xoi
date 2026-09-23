# Porcelain over the `uab-xoi` command (pyproject.toml, src/uab_xoi/). Other tasks live next to what
# they act on: docker/Makefile (image, dev containers) and tex/Makefile (single editions, snippets).
.PHONY: all build pdf serve clean

all: build

# PDFs + offline zips (build/xoi-uab-study-guide-<lang>.{pdf,zip}) + website (build/site), on the host.
build:
	uab-xoi build

# Only the PDFs and their offline zips (no website), on the host.
pdf:
	uab-xoi build --no-site

# Lean site (no PDFs, no zips) in Docker: http://localhost:65535/uab-xoi/. RELOAD=1 for live-reload.
serve:
	$(MAKE) -C docker serve

clean:
	uab-xoi clean
