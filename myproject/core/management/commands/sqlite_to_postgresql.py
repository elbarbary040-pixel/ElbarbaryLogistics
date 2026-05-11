"""
Export data from a legacy SQLite db.sqlite3 and load into PostgreSQL (DATABASE_URL).

Does not delete the SQLite file. Requires a writable MEDIA_ROOT for backups/fixtures.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.core.management.color import no_style
from django.db import connection

logger = logging.getLogger(__name__)


def _find_manage_py() -> Path:
    base = Path(settings.BASE_DIR)
    for cand in (base / "manage.py", base.parent / "manage.py"):
        if cand.is_file():
            return cand.resolve()
    raise CommandError("manage.py not found next to BASE_DIR or its parent.")


def _resolve_sqlite_path(explicit: str) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            raise CommandError(f"SQLite path not found: {p}")
        return p
    base = Path(settings.BASE_DIR)
    for cand in (base / "db.sqlite3", base.parent / "db.sqlite3"):
        if cand.is_file():
            return cand.resolve()
    raise CommandError(
        "db.sqlite3 not found. Pass --sqlite-path or set SQLITE_SOURCE_PATH."
    )


def _count_rows_json() -> dict[str, int]:
    out: dict[str, int] = {}
    for model in apps.get_models():
        if not model._meta.managed:
            continue
        label = model._meta.label_lower
        try:
            out[label] = model.objects.count()
        except Exception as exc:
            out[label] = -1
            logger.warning("Count failed for %s: %s", label, type(exc).__name__)
    return dict(sorted(out.items()))


def _run_sql_sequence_reset() -> None:
    models = [
        m
        for m in apps.get_models()
        if m._meta.managed and not m._meta.proxy
    ]
    sql_list = connection.ops.sequence_reset_sql(no_style(), models)
    if not sql_list:
        return
    with connection.cursor() as cursor:
        for stmt in sql_list:
            cursor.execute(stmt)


class Command(BaseCommand):
    help = (
        "Backup SQLite, dumpdata to JSON, migrate + flush PostgreSQL, loaddata, reset sequences."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default="",
            help="Path to db.sqlite3 (default: BASE_DIR/db.sqlite3 or parent)",
        )
        parser.add_argument(
            "--skip-sqlite-file-backup",
            action="store_true",
            help="Do not copy SQLite to MEDIA_ROOT/db_backups (still writes JSON fixture).",
        )
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Skip flush (only if PostgreSQL is empty; otherwise expect duplicate-key errors).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only backup SQLite + dumpdata + write counts; do not modify PostgreSQL.",
        )
        parser.add_argument(
            "--confirm-wipe-postgres",
            action="store_true",
            help="Required with default flush: confirms deleting all rows in PostgreSQL before import.",
        )

    def handle(self, *args, **options):
        sqlite_path = _resolve_sqlite_path(str(options.get("sqlite_path") or ""))
        dry_run = bool(options["dry_run"])
        no_flush = bool(options["no_flush"])
        confirm = bool(options["confirm_wipe_postgres"])
        skip_sqlite_copy = bool(options["skip_sqlite_file_backup"])

        if os.getenv("DJANGO_USE_SQLITE_EXPORT") == "1":
            raise CommandError(
                "Unset DJANGO_USE_SQLITE_EXPORT in this shell before running this command."
            )

        if not dry_run and not no_flush and not confirm:
            raise CommandError(
                "Refusing to flush PostgreSQL without --confirm-wipe-postgres. "
                "Use --no-flush only if the target DB is already empty."
            )

        manage_py = _find_manage_py()
        project_cwd = str(manage_py.parent)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = Path(settings.MEDIA_ROOT) / "db_backups"
        backup_root.mkdir(parents=True, exist_ok=True)

        if not skip_sqlite_copy:
            dest_sqlite = backup_root / f"sqlite_pre_pg_migrate_{stamp}.sqlite3"
            shutil.copy2(sqlite_path, dest_sqlite)
            self.stdout.write(self.style.SUCCESS(f"SQLite file backup: {dest_sqlite}"))
        else:
            self.stdout.write(self.style.WARNING("Skipped SQLite file copy (--skip-sqlite-file-backup)."))

        fixture_path = backup_root / f"pg_migrate_fixture_{stamp}.json"
        counts_sqlite_path = backup_root / f"pg_migrate_sqlite_counts_{stamp}.json"

        export_env = os.environ.copy()
        export_env["DJANGO_USE_SQLITE_EXPORT"] = "1"
        export_env["SQLITE_SOURCE_PATH"] = str(sqlite_path)
        export_env.pop("DATABASE_URL", None)
        export_env.setdefault("PYTHONUTF8", "1")
        export_env.setdefault("PYTHONIOENCODING", "utf-8")

        self.stdout.write("Exporting from SQLite (dumpdata)...")
        with open(fixture_path, "w", encoding="utf-8", newline="\n") as out_f:
            r = subprocess.run(
                [
                    sys.executable,
                    str(manage_py),
                    "dumpdata",
                    "--natural-foreign",
                    "--natural-primary",
                    "--indent",
                    "2",
                ],
                cwd=project_cwd,
                env=export_env,
                stdout=out_f,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        if r.returncode != 0:
            logger.error("dumpdata failed: %s", (r.stderr or "")[:2000])
            raise CommandError("dumpdata from SQLite failed; see logs / stderr.")

        self.stdout.write(self.style.SUCCESS(f"Fixture written: {fixture_path}"))

        count_prog = f"""
import json
import os
import sys
import django

os.environ["DJANGO_USE_SQLITE_EXPORT"] = "1"
os.environ["SQLITE_SOURCE_PATH"] = {str(sqlite_path)!r}
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
sys.path.insert(0, {project_cwd!r})
django.setup()
from django.apps import apps

d = {{}}
for m in apps.get_models():
    if not m._meta.managed:
        continue
    try:
        d[m._meta.label_lower] = m.objects.count()
    except Exception:
        d[m._meta.label_lower] = -1
print(json.dumps(dict(sorted(d.items()))))
"""
        r_counts = subprocess.run(
            [sys.executable, "-c", count_prog],
            cwd=project_cwd,
            env=export_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if r_counts.returncode != 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not capture SQLite row counts: {r_counts.stderr[:500]}"
                )
            )
        else:
            counts_sqlite_path.write_text(r_counts.stdout.strip(), encoding="utf-8")
            self.stdout.write(f"SQLite counts: {counts_sqlite_path}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: stopping before PostgreSQL changes."))
            return

        self.stdout.write("Running migrate on PostgreSQL...")
        call_command("migrate", interactive=False, verbosity=1)

        if not no_flush:
            self.stdout.write(self.style.WARNING("Flushing PostgreSQL data..."))
            call_command("flush", interactive=False, verbosity=1)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "--no-flush: existing PostgreSQL rows may cause loaddata conflicts."
                )
            )

        self.stdout.write("Loading fixture into PostgreSQL...")
        try:
            call_command("loaddata", str(fixture_path), verbosity=1)
        except Exception as exc:
            logger.error("loaddata failed: %s", type(exc).__name__)
            raise CommandError(
                f"loaddata failed: {type(exc).__name__}. Fixture preserved at {fixture_path}"
            ) from exc

        self.stdout.write("Resetting PostgreSQL sequences...")
        try:
            _run_sql_sequence_reset()
        except Exception as exc:
            logger.error("sequence reset failed: %s", type(exc).__name__)
            self.stdout.write(
                self.style.WARNING(
                    f"Sequence reset failed ({type(exc).__name__}); run sqlsequencereset manually."
                )
            )

        pg_counts = _count_rows_json()
        counts_pg_path = backup_root / f"pg_migrate_postgres_counts_{stamp}.json"
        counts_pg_path.write_text(json.dumps(pg_counts, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"PostgreSQL counts: {counts_pg_path}"))

        if counts_sqlite_path.is_file():
            try:
                sqlite_counts = json.loads(counts_sqlite_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                sqlite_counts = {}
            mismatches = []
            for k, v in sqlite_counts.items():
                if k not in pg_counts or pg_counts[k] != v:
                    mismatches.append((k, v, pg_counts.get(k)))
            if mismatches:
                self.stdout.write(self.style.WARNING("Row count mismatches (label, sqlite, postgres):"))
                for row in mismatches[:50]:
                    self.stdout.write(f"  {row}")
                if len(mismatches) > 50:
                    self.stdout.write(f"  ... and {len(mismatches) - 50} more")
            else:
                self.stdout.write(self.style.SUCCESS("Row counts match SQLite snapshot."))

        self.stdout.write(
            self.style.SUCCESS(
                "Done. Original SQLite file unchanged. Use DATABASE_URL (PostgreSQL) only in production."
            )
        )
