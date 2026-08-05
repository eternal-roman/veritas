# Container path for public deployment. The bare `veritas-server` default
# binds 127.0.0.1 deliberately (safe on a shared host); the container is the
# path that binds publicly, so it sets VERITAS_HOST itself.
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 veritas
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY veritas ./veritas

RUN pip install --no-cache-dir "."

USER veritas
ENV VERITAS_HOST=0.0.0.0 \
    VERITAS_PORT=8000 \
    VERITAS_RUNTIME_DIR=/home/veritas/runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["veritas-server"]
