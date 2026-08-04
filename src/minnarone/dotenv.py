"""Shared zero-dependency dotenv loading for Minnarone entrypoints."""

from __future__ import annotations

import os
from collections.abc import Collection
from pathlib import Path


def load_dotenv_file(path: Path, *, exclude_keys: Collection[str] = ()) -> list[str]:
    """Load unset environment variables from ``path`` without exposing values."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    loaded: list[str] = []
    excluded = frozenset(exclude_keys)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if key in excluded:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded


def load_env_files(
    config_path: str | None = None, *, exclude_keys: Collection[str] = ()
) -> None:
    """Load config-directory ``.env`` first, then cwd, preserving env precedence."""
    if config_path is not None:
        load_dotenv_file(
            Path(config_path).resolve().parent / ".env", exclude_keys=exclude_keys
        )
    load_dotenv_file(Path(".env"), exclude_keys=exclude_keys)
