import sqlite3
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy.engine import URL

from scripts import backup


def test_backup_contains_consistent_database_and_media(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "live.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('preserved')")

    media_root = tmp_path / "media"
    car_media = media_root / "cars"
    car_media.mkdir(parents=True)
    (car_media / "car.webp").write_bytes(b"webp-data")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "DATABASE_URL",
        str(URL.create("sqlite+aiosqlite", database=str(database_path))),
    )
    monkeypatch.setattr(backup, "MEDIA_DIR", media_root)
    monkeypatch.setattr(backup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))

    archive_path = backup.create_backup()

    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"database.sqlite3", "media/cars/car.webp"}
        extracted_database = tmp_path / "restored.sqlite3"
        extracted_database.write_bytes(archive.read("database.sqlite3"))
    with sqlite3.connect(extracted_database) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "preserved",
        )
    with ZipFile(archive_path) as archive:
        assert archive.read("media/cars/car.webp") == b"webp-data"
