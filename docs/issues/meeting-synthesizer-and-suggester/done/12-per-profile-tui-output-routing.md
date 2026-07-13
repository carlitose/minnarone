## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Route each profile's output to a separate `MinnaroneOutputStream` so the TUI
can display them in dedicated panels. The `TuiPrivateOutputRouter` learns to
dispatch messages to different streams based on the `CommentatorStyle` of the
Reactor that produced them.

## Step-by-step implementation plan

1. **Create per-profile `MinnaroneOutputStream` instances.**
   Instead of a single `MinnaroneOutputStream`, create one per active profile.
   Store them in a dict keyed by `CommentatorStyle`. The existing stream
   (used by OPERATOR / ORIGINAL_CHAT) becomes one entry in this dict.
   *Verify:* dict has the correct keys for the active profiles.
   *Pitfall:* the existing `MinnaroneOutputStream` API (append, recent_messages)
   stays unchanged — each stream instance is independent.

2. **Extend `TuiPrivateOutputRouter` to accept a style identifier.**
   The router needs to know which stream to write to. Options:
   - (A) Create one `TuiPrivateOutputRouter` per profile, each initialized
     with its own stream.
   - (B) Create a single router that receives the style as a parameter in
     `route()`.
   Option (A) is simpler and matches the multi-Reactor architecture (each
   Reactor has its own router). Each Reactor's `TuiPrivateOutputRouter` wraps
   a different `MinnaroneOutputStream`.
   *Verify:* two Reactors with different routers write to different streams.
   *Pitfall:* the PUBLIC routing (delegation to `public_router`) should only
   happen for styles that produce public output. The new styles are
   private-only.

3. **Wire per-profile routers in `build_agent`.**
   When building Reactors (slice 11), assign each Reactor a
   `TuiPrivateOutputRouter` wrapping the stream for its profile.
   *Verify:* `build_agent` produces Reactors with distinct routers.

4. **Expose streams for dashboard consumption.**
   The `DashboardState.snapshot()` needs access to per-profile streams to
   render their panels. Expose the streams dict on the Agent or pass them
   to the dashboard snapshot function.
   *Verify:* snapshot can read messages from each profile's stream.

5. **Write tests.**
   - Two profiles write to different streams.
   - Messages from one profile don't appear in the other's stream.
   - `recent_messages()` returns the correct messages per stream.
   Prior art: `test_output_sink.py` (TuiPrivateOutputRouter tests).

## Acceptance criteria

- [ ] Each active profile has its own `MinnaroneOutputStream`
- [ ] `TuiPrivateOutputRouter` instances route to separate streams
- [ ] Messages from different profiles don't mix
- [ ] Streams are accessible for dashboard rendering
- [ ] Existing OPERATOR/ORIGINAL_CHAT output routing unchanged

## Blocked by

- Blocked by [11-multi-reactor-parallel-wiring.md](./11-multi-reactor-parallel-wiring.md)

## User stories addressed

- User story 8
