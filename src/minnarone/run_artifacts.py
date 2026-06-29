"""Run-scoped local artifact paths for live observability sessions."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

DEFAULT_RUN_RETENTION_LIMIT = 20
DEFAULT_RUNS_ROOT = Path(".local") / "minnarone" / "runs"
OWNERSHIP_MARKER = ".minnarone-run"
_MARKER_PREFIX = "minnarone-run-artifacts-v1"
_ACTIVE_MARKER = f"{_MARKER_PREFIX}:active\n"
_COMPLETED_MARKER = f"{_MARKER_PREFIX}:completed\n"
_OWNED_RUN_DIR_RE = re.compile(r"^run-(\d{8}T\d{6}Z)-[0-9a-f]{8}$")


@dataclass(frozen=True, slots=True)
class RunSession:
    """Local artifact contract for one live runtime session."""

    run_dir: Path
    perception_log_path: Path
    debug_dir: Path
    started_at: datetime
    channel: str | None
    retention_limit: int

    def mark_completed(self) -> None:
        """Mark this run as completed so future startups may prune it."""
        _write_marker(self.run_dir, _COMPLETED_MARKER)


def create_run_session(
    *,
    root: str | Path = DEFAULT_RUNS_ROOT,
    channel: str | None = None,
    started_at: datetime | None = None,
    retention_limit: int = DEFAULT_RUN_RETENTION_LIMIT,
) -> RunSession:
    """Create a dedicated local artifact directory for one live run."""
    if (
        isinstance(retention_limit, bool)
        or not isinstance(retention_limit, int)
        or retention_limit < 1
    ):
        raise ValueError("retention_limit must be an integer >= 1")

    start = started_at or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)

    runs_root = Path(root)
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = _create_unique_run_dir(runs_root, start)
    _write_ownership_marker(run_dir)
    debug_dir = run_dir / "debug"
    debug_dir.mkdir()
    _prune_old_run_dirs(
        runs_root,
        active_run_dir=run_dir,
        keep_latest=retention_limit,
    )

    return RunSession(
        run_dir=run_dir,
        perception_log_path=run_dir / "perceptions.jsonl",
        debug_dir=debug_dir,
        started_at=start,
        channel=channel,
        retention_limit=retention_limit,
    )


def _create_unique_run_dir(root: Path, started_at: datetime) -> Path:
    stamp = started_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    for _ in range(100):
        run_dir = root / f"run-{stamp}-{uuid4().hex[:8]}"
        try:
            run_dir.mkdir()
        except FileExistsError:
            continue
        return run_dir
    raise RuntimeError("could not allocate a unique run artifact directory")


def _write_ownership_marker(run_dir: Path) -> None:
    _write_marker(run_dir, _ACTIVE_MARKER)


def _write_marker(run_dir: Path, content: str) -> None:
    (run_dir / OWNERSHIP_MARKER).write_text(content, encoding="utf-8")


def _prune_old_run_dirs(
    root: Path,
    *,
    active_run_dir: Path,
    keep_latest: int,
) -> None:
    active_runs = [
        path
        for path in root.iterdir()
        if _is_active_run_dir(path)
    ]
    completed = [
        path
        for path in root.iterdir()
        if _is_completed_run_dir(path)
    ]
    active = active_run_dir.resolve()
    other_completed_runs = [path for path in completed if path.resolve() != active]
    completed_budget = max(keep_latest - len(active_runs), 0)
    newest_completed_others = sorted(
        other_completed_runs,
        key=_run_sort_key,
        reverse=True,
    )[:completed_budget]
    keep = {active, *(path.resolve() for path in newest_completed_others)}

    for path in completed:
        if path.resolve() in keep:
            continue
        shutil.rmtree(path)


def _is_completed_run_dir(path: Path) -> bool:
    if not path.is_dir() or _OWNED_RUN_DIR_RE.fullmatch(path.name) is None:
        return False
    try:
        marker = (path / OWNERSHIP_MARKER).read_text(encoding="utf-8")
    except OSError:
        return False
    return marker == _COMPLETED_MARKER


def _is_active_run_dir(path: Path) -> bool:
    if not path.is_dir() or _OWNED_RUN_DIR_RE.fullmatch(path.name) is None:
        return False
    try:
        marker = (path / OWNERSHIP_MARKER).read_text(encoding="utf-8")
    except OSError:
        return False
    return marker == _ACTIVE_MARKER


def is_minnarone_run_dir(path: Path) -> bool:
    """Return whether `path` has a valid Minnarone run marker."""
    return _is_active_run_dir(path) or _is_completed_run_dir(path)


def _run_sort_key(path: Path) -> tuple[str, int, str]:
    match = _OWNED_RUN_DIR_RE.fullmatch(path.name)
    stamp = match.group(1) if match is not None else ""
    return (stamp, path.stat().st_mtime_ns, path.name)
