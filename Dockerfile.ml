# ── ML Worker Image ──────────────────────────────────────────────────────────
# Extends the base web image with the heavy data-science stack.
# Used only by the celery-ml-worker service; never by Gunicorn or the standard
# Celery worker.
#
# Keeping this separate means:
#   - Web / standard-worker images stay ~300-400 MB lighter per process
#   - ML dependencies (numpy, scikit-learn, prophet …) are never imported
#     in a web worker's address space

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies — includes libpq-dev for compiled psycopg2 and the
# C/Fortran toolchain that numpy/scipy require at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
        libpq-dev \
        libcairo2-dev \
        libpango1.0-dev \
        libglib2.0-0 \
        libffi-dev \
        libjpeg-dev \
        zlib1g-dev \
        pkg-config \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Install base web deps then layer the ML stack on top.
COPY requirements.txt requirements-prod.txt requirements-ml.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements-prod.txt \
    && pip install -r requirements-ml.txt

COPY . .

EXPOSE 8000
