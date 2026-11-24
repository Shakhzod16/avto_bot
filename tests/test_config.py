from pathlib import Path

from config import ENV_FILE


def test_env_file_is_next_to_project_root():
    assert ENV_FILE == Path(__file__).resolve().parents[1] / ".env"
