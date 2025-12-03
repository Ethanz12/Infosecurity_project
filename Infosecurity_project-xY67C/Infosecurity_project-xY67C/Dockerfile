# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12.3
FROM python:${PYTHON_VERSION}-slim as base

# Prevent .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Unbuffered stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------------
# Install system dependencies for mysqlclient
# -----------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
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

# Switch to non-root user
USER appuser

# Expose port for Gunicorn
EXPOSE 8000

# -----------------------------
# Gunicorn command
# -----------------------------
CMD ["gunicorn", "ISPJ_Web_App.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
