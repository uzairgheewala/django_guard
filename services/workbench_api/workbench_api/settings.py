from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "planguard-local-development-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [item for item in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if item]

ROOT_URLCONF = "workbench_api.urls"
WSGI_APPLICATION = "workbench_api.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "api.middleware.LocalCorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB", str(BASE_DIR / ".planguard-workbench.sqlite3")),
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PLANGUARD_STORE = Path(os.environ.get("PLANGUARD_STORE", BASE_DIR / "examples" / "store"))
PLANGUARD_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get(
        "PLANGUARD_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
)

PLANGUARD_INDEX = Path(
    os.environ.get("PLANGUARD_INDEX", PLANGUARD_STORE / "registry.sqlite3")
)

PLANGUARD_LAB_ENABLED = os.environ.get("PLANGUARD_LAB_ENABLED", "1" if DEBUG else "0") == "1"

PLANGUARD_PLAN_EXECUTION_ENABLED = os.environ.get("PLANGUARD_PLAN_EXECUTION_ENABLED", "0") == "1"

PLANGUARD_IMPORT_MAX_BYTES = int(os.environ.get("PLANGUARD_IMPORT_MAX_BYTES", "10000000"))
PLANGUARD_SECURITY_MAX_ARTIFACTS = int(os.environ.get("PLANGUARD_SECURITY_MAX_ARTIFACTS", "5000"))
PLANGUARD_QUARANTINE = Path(
    os.environ.get("PLANGUARD_QUARANTINE", PLANGUARD_STORE / "quarantine")
)
