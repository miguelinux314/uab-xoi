# Docker build/dev environment (see README.md here). Run from anywhere: make -C docker <target>.
# The root `make serve` calls `serve` below.
ROOT := $(abspath ..)
DEV_PORT ?= 65535
DEV_IMAGE = xoi-dev
DEV_CONTAINER = xoi-dev
# Host networking, so the raw-socket snippets see the host's interfaces (http://localhost:$(DEV_PORT)/uab-xoi/).
DEV_RUN = docker run --rm --network host -v "$(ROOT):/workspace/xoi.git"
DEV_TTY = $(shell [ -t 0 ] && echo -it)
# The repo is bind-mounted, not COPYd into the image: install the package editable at run time.
DEV_INSTALL = pip install -q --no-deps --no-build-isolation -e .

.PHONY: build serve shell pdf site run down

build:
	docker build -f $(ROOT)/docker/Dockerfile \
		--build-arg DEV_UID=$$(id -u) --build-arg DEV_GID=$$(id -g) \
		-t $(DEV_IMAGE) $(ROOT)

# Lean live-reloading site (no PDFs, no zips), after refreshing tex/code/snippets/*.out
serve: build
	$(DEV_RUN) $(DEV_TTY) --name $(DEV_CONTAINER) -e UAB_XOI_PORT=$(DEV_PORT) $(DEV_IMAGE)

shell:
	docker exec -it $(DEV_CONTAINER) bash

# PDFs and offline zips into build/
pdf:
	$(DEV_RUN) $(DEV_IMAGE) sh -c "$(DEV_INSTALL) && make -C tex code_output && uab-xoi build --no-site"

# PDFs, zips and the whole website into build/
site:
	$(DEV_RUN) $(DEV_IMAGE) sh -c "$(DEV_INSTALL) && make -C tex code_output && uab-xoi build"

# make -C docker run CMD="uab-xoi build --langs es"
run:
	$(DEV_RUN) $(DEV_TTY) $(DEV_IMAGE) sh -c "$(DEV_INSTALL) && $(CMD)"

down:
	docker stop $(DEV_CONTAINER)
