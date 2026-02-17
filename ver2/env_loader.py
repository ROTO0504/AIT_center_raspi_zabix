import os
from pathlib import Path


def _manual_load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        loaded = load_dotenv(env_path, override=True)
        if not loaded:
            _manual_load_env(env_path)
    except Exception:
        _manual_load_env(env_path)
