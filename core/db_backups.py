from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess

from django.conf import settings


def backup_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / "db_backups"
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_sqlite_backup(prefix: str = "manual") -> Path:

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_prefix = "".join(
        ch for ch in prefix
        if ch.isalnum() or ch in {"_", "-"}
    ).strip("_") or "manual"

    out = backup_dir() / f"backup_{safe_prefix}_{stamp}.json"

    with open(out, "w", encoding="utf-8") as f:

        subprocess.run(
            [
                "python",
                "manage.py",
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
            ],
            stdout=f,
            check=True,
        )

    return out