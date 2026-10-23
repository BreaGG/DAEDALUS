FROM python:3.12-slim

# No VOLUME instruction: Railway rejects it. Docker Compose mounts ./data at /data;
# on Railway, attach a volume and DAEDALUS uses its mount path (RAILWAY_VOLUME_MOUNT_PATH).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DAEDALUS_DEFAULT_DATA_DIR=/data \
    DAEDALUS_HOST=0.0.0.0 \
    DAEDALUS_RUN_AS=daedalus

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY daedalus ./daedalus
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 1000 daedalus \
    && mkdir -p /data && chown daedalus /data

# The process starts as root only to take ownership of the mounted data volume
# (Railway mounts volumes as root), then switches to the unprivileged "daedalus" user.
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/healthz' % (os.environ.get('DAEDALUS_PORT') or os.environ.get('PORT') or 8787))" || exit 1
CMD ["daedalus", "--no-browser"]
