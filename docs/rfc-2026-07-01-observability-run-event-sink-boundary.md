# RFC: Observability run-event sink boundary

## Problem

Run-event artifact writes are split across two parallel methods at every layer:

- `ArtifactWriter.write_trigger(...)`
- `ArtifactWriter.write_minnarone_output(...)`
- `NullArtifactWriter` and `FilesystemArtifactWriter` implement both.
- `_QueuedArtifactWriter` queues both with the same `run_events` stream.
- `_ReactionObserver` catches failures for both with the same `run_events`
  failure stream.

The on-disk schema is already owned by `RunEventLog` / `RunEventRecorder` in
`run_events.py`. `observability.py` should not grow another event model or
duplicate schema decisions, but it does need one deeper port for the run-event
artifact sink used by queueing and reaction observation.

## Proposed Interface

Keep the business-facing `ReactionObserver` API unchanged:

```python
def trigger(self, trigger: Trigger) -> None: ...
def minnarone_output(self, message: str, mode: OutputMode) -> None: ...
```

Add a structural run-event artifact sink in `observability.py`:

```python
class RunEventArtifactSink(Protocol):
    def record_trigger(self, trigger: Trigger) -> None: ...
    def record_minnarone_output(self, message: str, mode: OutputMode) -> None: ...
```

Change the artifact writer shape to expose a stable run-event sink:

```python
class ArtifactWriter(Protocol):
    @property
    def run_events(self) -> RunEventArtifactSink: ...

    def write_prompt(self, observation: PromptObservation) -> None: ...
    def write_summary_skip(self, exc: BaseException) -> None: ...

    # Compatibility shims retained in this slice:
    def write_trigger(self, trigger: Trigger) -> None: ...
    def write_minnarone_output(self, message: str, mode: OutputMode) -> None: ...
```

`FilesystemArtifactWriter.run_events` returns the existing `RunEventRecorder`
facade. `NullArtifactWriter.run_events` returns a no-op stable sink.

`_QueuedArtifactWriter.run_events` returns a queued sink that enqueues both
`record_trigger(...)` and `record_minnarone_output(...)` with stream
`run_events`. `_ReactionObserver` depends on `RunEventArtifactSink`, not the full
artifact writer.

The older `write_trigger(...)` and `write_minnarone_output(...)` methods remain
as compatibility shims that delegate to `.run_events`. They are not used by the
new internal path.

Rejected alternative: introduce tagged run-event dataclasses in
`observability.py`. That would duplicate the schema/event model already owned by
`run_events.py`.

Rejected alternative: migrate the entire `ArtifactWriter` to a generic
`write(Artifact)` union. It is cleaner long-term but too wide for this slice and
would break custom injected writers unnecessarily.

## Dependency Strategy

This is an in-process port split. It adds no new filesystem format, network,
LLM, Twitch, ffmpeg, PyAV, terminal UI, or model dependency.

`run_events.py` remains the schema owner for JSONL encoding/decoding,
redaction, sequence numbers, and replay. `observability.py` only chooses when to
queue and call the sink.

`RunEventArtifactSink` is structural and intentionally matches the existing
`RunEventRecorder` facade.

## Testing Strategy

- **New boundary tests to write**:
  - `RunObservability` accepts an injected writer that exposes only
    `.run_events.record_trigger(...)` /
    `.run_events.record_minnarone_output(...)` for run events.
  - `_ReactionObserver.trigger(...)` and
    `_ReactionObserver.minnarone_output(...)` both go through the queued
    `.run_events` sink.
  - run-event sink failures still do not block reactor routing or self-message
    tracking and still record `stream == "run_events"`.
  - queue overflow still records `stream == "run_events"` for trigger and output
    writes.
  - filesystem-backed observability writes trigger/output through
    `RunEventRecorder`; `RunEventLog.load()` can replay the artifacts.
- **Existing behavior to preserve**:
  - prompt artifact writer behavior and prompt failure stream;
  - summarizer skip failure behavior;
  - `flush()` / `aclose()` queue lifecycle;
  - `events.jsonl` schema and replay projections;
  - old `write_trigger(...)` / `write_minnarone_output(...)` compatibility
    methods.
- **Old tests to delete**: none.
- **Test environment needs**: in-memory fake writers and `tmp_path` for
  filesystem-backed writer checks. No Twitch, network, ffmpeg, PyAV, devices, or
  LLM calls.

## Implementation Recommendations

Add a private `_NullRunEventSink` and `_QueuedRunEventSink`.

Keep `_QueuedArtifactWriter` as the lifecycle/queue owner. Give it a stable
`run_events` sink created in `__init__`, not a new object per property access.

Update `_ReactionObserver` to accept `run_events: RunEventArtifactSink` and
remove direct dependency on full `ArtifactWriter`.

When preserving compatibility shims, implement them as:

```python
def write_trigger(self, trigger: Trigger) -> None:
    self.run_events.record_trigger(trigger)
```

Do not add new public exports unless tests require importing the protocol from
`minnarone.observability`; keep the package root export unchanged.
