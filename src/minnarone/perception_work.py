"""Cancellation context for queued local perception work."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import count
from threading import RLock


@dataclass(frozen=True, slots=True)
class PerceptionWorkToken:
    """Identity token for one queued perception job."""

    id: int


_next_token_id = count(1)
_current_token: ContextVar[PerceptionWorkToken | None] = ContextVar(
    "minnarone_perception_work_token",
    default=None,
)
_cancelled_token_ids: set[int] = set()
_token_lock = RLock()


def new_perception_work_token() -> PerceptionWorkToken:
    """Create a fresh token for one queued processor invocation."""
    return PerceptionWorkToken(next(_next_token_id))


@contextmanager
def perception_work_scope(token: PerceptionWorkToken):
    """Expose `token` to code running inside a queued processor."""
    reset = _current_token.set(token)
    try:
        yield
    finally:
        _current_token.reset(reset)


def cancel_perception_work(token: PerceptionWorkToken) -> None:
    """Mark a queued processor invocation as no longer allowed to write."""
    with _token_lock:
        _cancelled_token_ids.add(token.id)


def clear_perception_work(token: PerceptionWorkToken) -> None:
    """Forget a completed non-cancelled processor token."""
    with _token_lock:
        _cancelled_token_ids.discard(token.id)


def current_perception_work_cancelled() -> bool:
    """Return whether the current processor context was cancelled."""
    token = _current_token.get()
    if token is None:
        return False
    with _token_lock:
        return token.id in _cancelled_token_ids
