# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12.3
FROM python:${PYTHON_VERSION}-slim as base

# Prevent .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Unbuffered stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------------
# Install system dependencies for mysqlclient, mysqladmin, and dos2unix and Tesseract OCR
# -----------------------------
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

# -----------------------------
# Copy source code
# -----------------------------
COPY . .

# -----------------------------
# Copy entrypoint script
# Convert Windows line endings to Linux line endings and make executable
# -----------------------------
COPY entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port for Gunicorn
EXPOSE 8000

# -----------------------------
# Use entrypoint to wait for MySQL and run migrations
# -----------------------------
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "ISPJ_Web_App.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
