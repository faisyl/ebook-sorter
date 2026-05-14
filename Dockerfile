FROM python:3.12-slim AS builder

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

WORKDIR /build

COPY pyproject.toml .
COPY src/ src/

RUN SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION} \
    pip install --no-cache-dir build && \
    SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION} \
    python -m build --wheel --outdir /build/dist


FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/faisyl/ebook-sorter"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        djvulibre-bin \
        p7zip-full \
        calibre \
        gosu \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc/* /usr/share/man/*

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

COPY <<'EOF' /entrypoint.sh
#!/bin/sh
if [ -n "$PUID" ] && [ -n "$PGID" ]; then
    groupadd -o -g "$PGID" ebook 2>/dev/null
    useradd -o -u "$PUID" -g "$PGID" -m ebook 2>/dev/null
    exec gosu ebook ebook-sorter "$@"
else
    exec ebook-sorter "$@"
fi
EOF
RUN chmod +x /entrypoint.sh

WORKDIR /data

ENTRYPOINT ["/entrypoint.sh"]
