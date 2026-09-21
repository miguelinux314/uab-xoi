# Docker build/dev environment

`docker/Dockerfile` is a Debian 13 image with everything needed to build the PDFs, the offline zips
and the site: TeX Live (the subset listed in `requirements_apt.txt`), mscgen, pandoc, dvisvgm/poppler
and a Python venv with the dependencies declared in `pyproject.toml`. The repository is bind-mounted
at `/workspace/xoi.git` (nothing is copied into the image) and the `uab-xoi` package is installed
editable inside the container at run time (`pip install -e .`), so host edits apply immediately.

The same image is used by `.github/workflows/deploy.yml`, so what builds locally builds in CI. The
local `make serve` and the other `docker/Makefile` targets also run with `--network host` and the venv python has `CAP_NET_RAW`, so
`make -C tex code_output` (re-running `tex/code/snippets/*.py`, including the raw Ethernet-socket ones on the
interface named in the snippets) works without sudo.

## Targets (root `Makefile`)

- `make -C docker build` - build the image (`xoi-dev`), with your host UID/GID so generated files are yours.
- `make serve` - serve the site at `http://localhost:65535/uab-xoi/` (`DEV_PORT` to change) with
  `uab-xoi serve`: lean, no PDFs or zips; sources are regenerated when a file changes.
- `make -C docker shell` - shell into the running container.
- `make -C docker pdf` - PDFs and offline zips into `build/`.
- `make -C docker site` - PDFs, zips and the whole website into `build/`.
- `make -C docker run CMD="uab-xoi build --langs es"` - any command inside the container.
- `make -C docker down` - stop the container.

No SSH agent, git identity or credentials are mounted: commit and push from the host.
