"""Create a consistent SQLite and media ZIP backup."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.engine import make_url

from backend.app.core.config import DATABASE_URL, MEDIA_DIR, PROJECT_ROOT


def _database_path() -> Path:
    url = make_url(DATABASE_URL)
    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or url.database == ":memory:"
    ):
        raise RuntimeError("Zaxira nusxasi faqat faylli SQLite bazasi uchun sozlangan")
    raw_path = unquote(url.database)
    if (
        os.name == "nt"
        and len(raw_path) > 2
        and raw_path[0] == "/"
        and raw_path[2] == ":"
    ):
        raw_path = raw_path[1:]
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def create_backup() -> Path:
    """Write a consistent database snapshot and media files to a timestamped ZIP."""
    database_path = _database_path()
    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite bazasi topilmadi: {database_path}")
    backup_dir = Path(os.getenv("BACKUP_DIR", str(PROJECT_ROOT / "backups")))
    if not backup_dir.is_absolute():
        backup_dir = PROJECT_ROOT / backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archive_path = backup_dir / f"buxara-backup-{timestamp}.zip"

    with tempfile.TemporaryDirectory(prefix="buxara-backup-") as temp_dir:
        database_copy = Path(temp_dir) / "database.sqlite3"
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(database_copy)) as destination,
        ):
            source.backup(destination)
            destination.commit()
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.write(database_copy, arcname="database.sqlite3")
            if MEDIA_DIR.is_dir():
                media_root = MEDIA_DIR.resolve()
                for path in MEDIA_DIR.rglob("*"):
                    if not path.is_file():
                        continue
                    resolved = path.resolve()
                    if media_root not in resolved.parents:
                        continue
                    archive.write(
                        path, arcname=Path("media") / path.relative_to(MEDIA_DIR)
                    )
    return archive_path


def main() -> None:
    """Run the backup command and print the created archive path."""
    print(create_backup())


if __name__ == "__main__":
    main()
