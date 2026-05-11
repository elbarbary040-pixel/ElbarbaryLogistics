from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


def backup_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / "db_backups"
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_database_backup(prefix: str = "manual") -> Path:
    """Write a JSON fixture via dumpdata (works with PostgreSQL and any Django DB backend)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = (
        "".join(ch for ch in prefix if ch.isalnum() or ch in {"_", "-"}).strip("_")
        or "manual"
    )
    out = backup_dir() / f"backup_{safe_prefix}_{stamp}.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            call_command(
                "dumpdata",
                natural_foreign=True,
                natural_primary=True,
                stdout=f,
            )
    except Exception as exc:
        logger.error(
            "dumpdata backup failed (prefix=%s): %s",
            safe_prefix,
            type(exc).__name__,
        )
        out.unlink(missing_ok=True)
        raise
    return out
