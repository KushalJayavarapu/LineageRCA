"""Logical clock: simulated time that moves one minute per tick. We never read the wall clock inside data or metadata."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# A fixed, arbitrary start so every run with the same seed produces identical timestamps.
EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class LogicalClock:
    """Counts ticks. Each commit to a table calls tick() once."""

    def __init__(self) -> None:
        self._ticks = 0

    def tick(self) -> int:
        """Advance by one minute and return the new tick number."""
        self._ticks += 1
        return self._ticks

    @property
    def now(self) -> int:
        return self._ticks

    @staticmethod
    def as_datetime(tick: int) -> datetime:
        """Human-readable form of a tick (for reports only)."""
        return EPOCH + timedelta(minutes=tick)
