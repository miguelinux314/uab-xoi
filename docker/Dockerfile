# Build/dev image for the study guide: TeX Live + pandoc + mkdocs. No translation tooling
# (that is maintainer-only).
# The repo is never COPYd in: it is bind-mounted at /workspace/xoi.git by `make dev*` and by the GitHub Actions
# workflow, so the same image builds locally and in CI.
FROM debian:13-slim

COPY docker/requirements_apt.txt /tmp/requirements_apt.txt
RUN apt-get update \
    && grep -Ev '^\s*(#|$)' /tmp/requirements_apt.txt \
        | xargs apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements_apt.txt

# A venv sidesteps Debian's PEP 668 restriction on bare `pip install`.
# pygmentize from this venv is what minted shells out to.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# Runtime dependencies come from pyproject.toml; the package itself is installed editable at run
# time (the repo is bind-mounted), see DEV_INSTALL in the Makefile and the CI workflow.
COPY pyproject.toml /tmp/pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/deps.txt \
    && pip install --no-cache-dir setuptools wheel -r /tmp/deps.txt \
    && rm /tmp/pyproject.toml /tmp/deps.txt

# code/snippets/ethernet*.py open raw sockets: give python CAP_NET_RAW so
# `make code_output` works as the dev user (the Makefile's CODE_PY default is
# `sudo python`; here plain python suffices). Needs `--network host` at run
# time so the interface named in the snippets exists.
RUN setcap cap_net_raw+ep "$(readlink -f $VIRTUAL_ENV/bin/python)"
ENV CODE_PY=python

# Non-root user matching the host UID/GID (passed by the root Makefile), so
# files written through the bind mount are owned by the host user.
ARG DEV_UID=1000
ARG DEV_GID=1000
RUN groupadd --gid "$DEV_GID" dev \
    && useradd --uid "$DEV_UID" --gid "$DEV_GID" --create-home --shell /bin/bash dev \
    && chown -R dev:dev "$VIRTUAL_ENV"  # so `pip install -e .` works at run time
USER dev

WORKDIR /workspace/xoi.git
# Refresh the snippet outputs embedded in the book, then serve the site (lean: no PDFs or zips).
CMD ["sh", "-c", "pip install -q --no-deps --no-build-isolation -e . && (make -C tex code_output || echo 'warning: code_output failed; using the committed .out files' >&2); exec uab-xoi serve --host 0.0.0.0"]
