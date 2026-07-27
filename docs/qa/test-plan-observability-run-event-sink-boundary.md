# QA Test Plan: Observability run-event sink boundary

## Scope

- RFC: `docs/rfc-2026-07-01-observability-run-event-sink-boundary.md`
- Code: `src/minnarone/observability.py`
- Tests: `tests/test_observability.py`

## Automated Checks

- RED: `uv run pytest tests/test_observability.py -k 'run_event_sink or run_event_failure_for_each_action or filesystem_run_event_sink'`
  - Expected before implementation: injected writer with only `.run_events`
    receives no run-event calls and run-event sink failures are not surfaced.
  - Observed: 2 failures matching the old split-method path.
- GREEN: `uv run pytest tests/test_observability.py -k 'run_event_sink or run_event_failure_for_each_action or filesystem_run_event_sink'`
  - Observed: 5 passed, 54 deselected.
- Observability regression: `uv run pytest tests/test_observability.py`
  - Observed: 59 passed.
- Run-event/replay schema regression:
  - `uv run pytest tests/test_run_events.py tests/test_replay.py -k 'run_event or replay_loads_run_event or multiline_minnarone_output or legacy_run_event'`
  - Observed: 8 passed, 10 deselected.
- Static checks:
  - `uv run ruff check src/minnarone/observability.py tests/test_observability.py`
    - Observed: passed.
  - `uv run ruff format --check src/minnarone/observability.py tests/test_observability.py`
    - Observed: 2 files already formatted after applying formatter.

## Manual Review Checklist

- `ReactionObserver` caller API remains unchanged.
- `ArtifactWriter.write_trigger(...)` and `write_minnarone_output(...)` remain
  available as compatibility shims.
- New internal path uses a stable `.run_events` sink for queued trigger/output
  artifacts.
- Legacy injected writers without `.run_events` are adapted through the old
  split methods.
- `FilesystemArtifactWriter.run_events` returns the existing
  `RunEventRecorder`; `events.jsonl` schema remains owned by `run_events.py`.
- Run-event queue failures still use `stream == "run_events"` and do not block
  business routing or self-message tracking.
- Prompt and summarizer artifact behavior is unchanged.

## Full Quality Gate

- Pending: `make quality`.
