# Container path for public deployment. The bare `veritas-server` default
# binds 127.0.0.1 deliberately (safe on a shared host); the container is the
# path that binds publicly, so it sets VERITAS_HOST itself.
# Pinned by digest, not by tag. `python:3.12-slim` is a moving pointer: the
# same Dockerfile built twice can produce images with different base contents,
# which is the same mutable-reference problem the Action SHAs and the
# dependency lock exist to remove. This is the OCI image index digest, so
# multi-architecture builds still resolve normally. Dependabot's docker
# ecosystem bumps it, so pinning does not mean missing base-image security
# updates — see .github/dependabot.yml.
FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

RUN useradd --create-home --uid 1000 veritas
WORKDIR /app

# Dependencies first, from the hashed lock. `pip install "."` resolved the
# pyproject floors against PyPI at build time, so two builds of one commit
# could ship different dependency trees, and a compromised release of any
# transitive dependency landed in the image unreviewed. --require-hashes makes
# a substituted artifact fail the build instead of shipping.
#
# This is also the layer that changes least, so it caches across source edits.
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY pyproject.toml README.md LICENSE ./
COPY veritas ./veritas

# --no-deps because every dependency is already installed above; resolving
# again here would quietly reintroduce the unpinned floor path this change
# exists to remove. `pip check` then proves the locked closure actually
# satisfies what the package declares, so drift between pyproject and
# requirements.lock fails the build rather than the container's first request.
RUN pip install --no-cache-dir --no-deps "." \
    && pip check

USER veritas
ENV VERITAS_HOST=0.0.0.0 \
    VERITAS_PORT=8000 \
    VERITAS_RUNTIME_DIR=/home/veritas/runtime

# The runtime directory holds the financial ledger, the custody receipts and
# the trust counters. In the container's writable layer they vanish when it is
# replaced, taking the record of what was earned with them.
VOLUME ["/home/veritas/runtime"]

EXPOSE 8000

# Liveness, not readiness: a misconfigured instance is alive and should not be
# restarted, it should be left out of rotation. Orchestrators read /readyz for
# that (see veritas/server.py).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["veritas-server"]
