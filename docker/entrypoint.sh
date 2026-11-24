#!/bin/sh
set -eu

python -m alembic upgrade head
python -m backend.app.seed --if-empty
exec python main.py
