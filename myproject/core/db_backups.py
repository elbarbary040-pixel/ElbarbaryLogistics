from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from django.conf import settings


def backup_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / "db_backups"
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_sqlite_backup(prefix: str = "manual") -> Path:
    db_path = Path(settings.BASE_DIR) / "db.sqlite3"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in {"_", "-"}).strip("_") or "manual"
    out = backup_dir() / f"db_{safe_prefix}_{stamp}.sqlite3.bak"
    shutil.copy2(db_path, out)
    return out

