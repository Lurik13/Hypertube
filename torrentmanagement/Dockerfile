# Build the API runtime with a pinned Python base image and FFmpeg.
FROM python:3.13-slim-trixie@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TM_DATA_DIR=/data

# Install the media tooling before dropping all application privileges.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg=7:7.1.5-0+deb13u1 \
        libpq5=17.12-0+deb13u1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install exactly the dependency set recorded for this POC.
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY app ./app
COPY static ./static
COPY tests ./tests

# Catch syntax errors during image creation, before the service starts.
RUN python -m compileall -q app tests

# The application runs non-root and writes only to the mounted data volume.
RUN mkdir -p /data \
    && useradd --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin torrent \
    && chown -R torrent:torrent /data /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "critical"]
