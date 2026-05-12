"""
Django settings for myproject project.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ================= SECURITY =================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")

DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    "proud-creation-production-3d68.up.railway.app",
    ".railway.app",
]

CSRF_TRUSTED_ORIGINS = [
    "https://proud-creation-production-3d68.up.railway.app",
]

# ================= APPS =================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "orders.apps.OrdersConfig",
    "merchants",
    "delegates",
    "core",
]

# ================= MIDDLEWARE =================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # custom middleware (لو فيه مشكلة هنا هنرجع نشيله لاحقاً)
    "core.middleware.ExceptionCaptureMiddleware",
    "core.middleware.ClientSessionMiddleware",
    "core.middleware.PartnerAccessControlMiddleware",
    "core.middleware.AuditTrailMiddleware",
]

ROOT_URLCONF = "myproject.urls"

# ================= TEMPLATES =================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_branding",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"

# ================= DATABASE =================
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("DATABASE_PUBLIC_URL")
)

if not DATABASE_URL:
    # بدل ما يوقع السيرفر → نخليه fail واضح في اللوج فقط
    print("❌ WARNING: DATABASE_URL is missing")
else:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=os.getenv("DATABASE_SSL_REQUIRE", "true").lower()
            in ("1", "true", "yes"),
        )
    }

# ================= PASSWORDS =================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ================= INTERNATIONAL =================
TIME_ZONE = "Africa/Cairo"
LANGUAGE_CODE = "ar"

USE_I18N = True
USE_TZ = True

# ================= STATIC =================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ================= AUTH =================
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# ================= PRODUCTION SECURITY =================
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ================= STATIC STORAGE =================
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ================= LOGGING =================
print("STARTING APP")
print("DEBUG =", DEBUG)
print("DATABASE_URL =", DATABASE_URL)