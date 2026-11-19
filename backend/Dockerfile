# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.15.0+cpu" \
    && pip install -r /tmp/requirements-runtime.txt \
    && pip check

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /var/lib/realtyai/chroma && chown -R app:app /var/lib/realtyai
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_CACHE=/opt/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    REALTYAI_VECTOR_DB_DIR=/var/lib/realtyai/chroma \
    REALTYAI_COLLECTION_NAME=realtyai_multisource_v1 \
    REALTYAI_COLLECTION_ID=51cdb05c-3ee9-4b04-b85c-71cbf168ff0d \
    PORT=8000
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=app:app backend /app/backend
COPY deployment/model-cache/hub /opt/models/hub
RUN chmod -R a-w /opt/models && chmod 755 /app/backend/container-entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/ready',timeout=8).read()"]
ENTRYPOINT ["/app/backend/container-entrypoint.sh"]
