# One image for the api and the worker (different command in docker-compose.yml).
FROM python:3.13.18-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --root-user-action=ignore -r requirements.txt

# Non-root user; /data/media is created here so the named volume inherits its owner.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/media \
    && chown app:app /data/media

COPY alembic.ini entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
RUN python -m compileall -q app alembic

USER 10001:10001
EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# `make test` image: runtime plus pytest and the test suite.
FROM runtime AS test
USER root
COPY requirements-dev.txt .
RUN pip install --root-user-action=ignore -r requirements-dev.txt
COPY pytest.ini ./
COPY tests ./tests
USER 10001:10001
CMD ["pytest"]
