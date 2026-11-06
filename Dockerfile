# syntax=docker/dockerfile:1
#
# Galactic Feed in un solo container: il server (Python + FastAPI) serve anche la PWA.
# Architetture: linux/amd64, linux/arm64, linux/arm/v7.
#
#   docker build -t galactic-feed .
#   docker run -p 8080:8080 -v galactic-data:/data -e PUBLIC_URL=http://localhost:8080 galactic-feed

ARG PYTHON_IMAGE=python:3.12-slim-trixie
ARG PYTHON_BUILD_IMAGE=python:3.12-trixie
ARG NODE_IMAGE=node:22-trixie-slim

# ---------- 1. La PWA ----------
# È la stessa per tutte le architetture: si compila una volta, sulla macchina che fa la build.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS pwa
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Le dipendenze Python ----------
# Si usa l'immagine Python completa, che ha già il compilatore C: su armv7 tre pacchetti
# (argon2-cffi-bindings, cffi, regex) non sono pronti e vanno compilati. Altrove pip scarica
# solo pacchetti già pronti. Nell'immagine finale passa solo il risultato (/opt/venv).
FROM ${PYTHON_BUILD_IMAGE} AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt

# ---------- 3. L'immagine finale ----------
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="Galactic Feed" \
      org.opencontainers.image.description="Lettore di notizie self-hosted e multiutente: feed RSS e canali YouTube in una PWA." \
      org.opencontainers.image.source="https://github.com/TehMaat/galactic-feed"

# L'immagine slim ha già tzdata, per gli orari giusti nel log secondo TZ.
RUN groupadd --system --gid 1000 galactic \
    && useradd --system --uid 1000 --gid galactic --home-dir /data --no-create-home --shell /usr/sbin/nologin galactic \
    && mkdir -p /data && chown galactic:galactic /data

COPY --from=deps /opt/venv /opt/venv
COPY VERSION /app/VERSION
COPY backend/app /app/backend/app
COPY --from=pwa /src/frontend/dist /app/frontend
RUN /opt/venv/bin/python -m compileall -q /app/backend/app

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    FRONTEND_DIR=/app/frontend \
    HOST=0.0.0.0 \
    PORT=8080 \
    TZ=Europe/Rome

WORKDIR /app/backend
USER galactic
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD ["python", "-m", "app.healthcheck"]

CMD ["python", "-m", "app"]
