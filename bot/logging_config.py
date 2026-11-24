"""Bot uchun konsol va aylanuvchi fayl loglash."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: str | Path = "logs") -> None:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    if not any(isinstance(handler, logging.StreamHandler) for handler in root.handlers):
        root.addHandler(console)

    file_handler = RotatingFileHandler(
        directory / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        root.addHandler(file_handler)
