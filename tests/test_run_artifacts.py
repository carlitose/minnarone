from datetime import UTC, datetime, timedelta
from pathlib import Path

from minnarone.run_artifacts import (
    DEFAULT_RUNS_ROOT,
    OWNERSHIP_MARKER,
    create_run_session,
)


def test_create_run_session_creates_run_local_artifact_paths(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    started_at = datetime(2026, 6, 29, 10, 30, 5, tzinfo=UTC)
    channel = "https://twitch.tv/minnarone?oauth_token=secret"

    session = create_run_session(
        root=root,
        channel=channel,
        started_at=started_at,
    )

    assert session.run_dir.is_dir()
    assert (session.run_dir / OWNERSHIP_MARKER).is_file()
    assert (session.run_dir / OWNERSHIP_MARKER).read_text(encoding="utf-8").endswith(
        ":active\n"
    )
    assert session.run_dir.parent == root
    assert session.perception_log_path == session.run_dir / "perceptions.jsonl"
    assert session.debug_dir == session.run_dir / "debug"
    assert session.debug_dir.is_dir()
    assert session.started_at == started_at
    assert session.channel == channel
    assert session.retention_limit == 20
    assert "minnarone" not in session.run_dir.name
    assert "secret" not in session.run_dir.name


def test_create_run_session_keeps_only_latest_twenty_owned_runs_by_default(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    base = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)

    sessions = [
        create_run_session(root=root, started_at=base + timedelta(minutes=index))
        for index in range(22)
    ]
    for session in sessions:
        session.mark_completed()
    create_run_session(root=root, started_at=base + timedelta(minutes=30))

    remaining = sorted(path.name for path in root.iterdir() if path.is_dir())
    assert len(remaining) == 20
    assert not sessions[0].run_dir.exists()
    assert not sessions[1].run_dir.exists()
    assert sessions[-1].run_dir.exists()


def test_create_run_session_never_prunes_active_run_or_unowned_directories(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    root.mkdir(parents=True)
    unrelated = root / "operator-notes"
    unrelated.mkdir()
    ambiguous = root / "run-20260629T100000Z-00000000"
    ambiguous.mkdir()
    owned = root / "run-20260629T100100Z-00000001"
    owned.mkdir()
    (owned / OWNERSHIP_MARKER).write_text(
        "minnarone-run-artifacts-v1:completed\n",
        encoding="utf-8",
    )
    corrupt = root / "run-20260629T100200Z-00000002"
    corrupt.mkdir()
    (corrupt / OWNERSHIP_MARKER).write_text("not ours\n", encoding="utf-8")

    session = create_run_session(
        root=root,
        started_at=datetime(2026, 6, 29, 9, 0, tzinfo=UTC),
        retention_limit=1,
    )

    assert session.run_dir.exists()
    assert unrelated.exists()
    assert ambiguous.exists()
    assert corrupt.exists()
    assert not owned.exists()


def test_create_run_session_never_prunes_other_active_runs(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    base = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)
    still_active = create_run_session(root=root, started_at=base)
    completed = create_run_session(root=root, started_at=base + timedelta(minutes=1))
    completed.mark_completed()

    current = create_run_session(
        root=root,
        started_at=base + timedelta(minutes=2),
        retention_limit=1,
    )

    assert current.run_dir.exists()
    assert still_active.run_dir.exists()
    assert not completed.run_dir.exists()


def test_active_runs_consume_retention_budget_without_being_pruned(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    base = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)
    active_a = create_run_session(root=root, started_at=base)
    active_b = create_run_session(root=root, started_at=base + timedelta(minutes=1))
    completed = create_run_session(root=root, started_at=base + timedelta(minutes=2))
    completed.mark_completed()

    current = create_run_session(
        root=root,
        started_at=base + timedelta(minutes=3),
        retention_limit=2,
    )

    assert current.run_dir.exists()
    assert active_a.run_dir.exists()
    assert active_b.run_dir.exists()
    assert not completed.run_dir.exists()


def test_active_run_consumes_one_retention_slot_even_when_older(tmp_path):
    root = tmp_path / ".local" / "minnarone" / "runs"
    base = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)

    for index in range(3):
        session = create_run_session(
            root=root,
            started_at=base + timedelta(minutes=index),
            retention_limit=20,
        )
        session.mark_completed()

    active = create_run_session(
        root=root,
        started_at=base - timedelta(hours=1),
        retention_limit=3,
    )

    remaining = [path for path in root.iterdir() if path.is_dir()]
    assert len(remaining) == 3
    assert active.run_dir.exists()


def test_default_run_artifacts_are_under_gitignored_local_data():
    ignored_patterns = {
        line.strip()
        for line in Path(".gitignore").read_text(encoding="utf-8").splitlines()
    }

    assert DEFAULT_RUNS_ROOT.parts[0] == ".local"
    assert ".local/" in ignored_patterns
