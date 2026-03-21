FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies required by WeasyPrint (PDF), psycopg2, and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
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

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install xhtml2pdf gunicorn

# Source code is bind-mounted in development; copied in production builds
COPY . .

EXPOSE 8000
