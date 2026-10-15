"""Optional local progress observers; never change audio or create another queue."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_sink = ContextVar("ocf_progress_sink", default=None)
_counts = ContextVar("ocf_progress_counts", default=None)


@contextmanager
def observing(sink):
    token = _sink.set(sink)
    counts = _counts.set({})
    try:
        yield
    finally:
        _counts.reset(counts)
        _sink.reset(token)


def report(phase: str, *, completed=None, total=None, detail=None):
    sink = _sink.get()
    if sink is None:
        return
    row = {"phase": phase[:80]}
    if completed is not None:
        row["completed"] = int(completed)
    if total is not None:
        row["total"] = int(total)
    if detail is not None:
        row["detail"] = str(detail)[:160]
    try:
        sink(row)
    except OSError:
        # Observer I/O must not interrupt synthesis or mutate its output.
        pass


def advance(phase: str, *, detail=None):
    if _sink.get() is None:
        return
    counts = _counts.get()
    counts[phase] = counts.get(phase, 0) + 1
    report(phase, completed=counts[phase], detail=detail)
