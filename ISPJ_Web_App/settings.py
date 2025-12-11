"""
Django settings for ISPJ_Web_App project.
Secure configuration for government-focused web application.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# SECURITY & ENVIRONMENT CONFIGURATION
# ============================================================

# Secret key
SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-development-key")

# Proper DEBUG handling
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

# Allowed hosts (Docker compatible)
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost"
).split(",")

# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.home",

    # Future internal apps (you will add these)
    # "encryption",          # AES-256 field-level encryption
    # "classification",      # AI-based data classification
    # "messaging",           # Secure E2EE chat + file transfer
    # "dlp",                 # Data loss prevention + redaction
    # "audit",               # Compliance logging
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ISPJ_Web_App.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # You may add templates folder
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ISPJ_Web_App.wsgi.application"

# ============================================================
# DATABASE (MYSQL for Docker)
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", "securegov"),
        "USER": os.environ.get("MYSQL_USER", "secureuser"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "password"),
        "HOST": os.environ.get("MYSQL_HOST", "mysql"),  # docker-compose service name
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Singapore"
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC & MEDIA FILES
# ============================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ============================================================
# SECURITY HEADERS (Required for government-grade apps)
# ============================================================

# if not DEBUG:  # only enforce in production
#     SECURE_SSL_REDIRECT = True
#     SESSION_COOKIE_SECURE = True
#     CSRF_COOKIE_SECURE = True
#     SECURE_HSTS_SECONDS = 31536000  # 1 year
#     SECURE_HSTS_INCLUDE_SUBDOMAINS = True
#     SECURE_HSTS_PRELOAD = True
#     X_FRAME_OPTIONS = "DENY"
#     SECURE_CONTENT_TYPE_NOSNIFF = True
#     SECURE_BROWSER_XSS_FILTER = True

# ============================================================
# DEFAULT PRIMARY KEY TYPE
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
