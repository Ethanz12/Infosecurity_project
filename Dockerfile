# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12.3
FROM python:${PYTHON_VERSION}-slim as base

# Prevent .pyc files and buffer issues
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------------
# Install system dependencies
# -----------------------------
# We install default-mysql-client for the entrypoint 'ping' check
# We install dos2unix to fix Windows line ending issues in scripts
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    default-mysql-client \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Create non-root user
# -----------------------------
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# -----------------------------
# Install Python dependencies
# -----------------------------
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Install spaCy + English model
RUN pip install spacy && \
    python -m spacy download en_core_web_sm

# -----------------------------
# Copy source code
# -----------------------------
COPY . .

# -----------------------------
# CRITICAL PERMISSION FIX
# -----------------------------
# Since we run 'makemigrations' inside the container as 'appuser',
# 'appuser' needs write permission to the /app folder to create the files.
RUN chown -R appuser:appuser /app

# -----------------------------
# Setup Entrypoint Script
# -----------------------------
COPY entrypoint.sh /entrypoint.sh
# Fix Windows line endings (CRLF -> LF) and make executable
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# -----------------------------
# Use entrypoint
# -----------------------------
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["gunicorn", "ISPJ_Web_App.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]