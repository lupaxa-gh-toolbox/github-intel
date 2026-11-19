"""
Shared GitHub primary and secondary rate-limit pauses.

Every concurrent request waits on the same controller.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import time

__all__ = [
    "RateLimitController",
]


class RateLimitController:
    """Track remaining quota and pause every worker when GitHub asks."""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], asyncio.Future[None]] | None = None,
    ) -> None:
        """
        Create a controller.

        Args:
            clock: Monotonic clock, replaced in tests.
            sleeper: Sleep coroutine, replaced in tests.

        """

        self._clock = clock or time.monotonic
        self._sleep = sleeper or asyncio.sleep
        self._pause_until = 0.0
        self._lock = asyncio.Lock()
        self._on_wait: Callable[[float], None] | None = None
        self.pauses = 0

    def observe(
        self,
        status: int,
        headers: dict[str, str],
        now: float | None = None,
    ) -> None:
        """
        Record rate-limit headers from one response.

        Args:
            status: HTTP status.
            headers: Response headers with lower-case names.
            now: Epoch time used to interpret ``X-RateLimit-Reset``.

        """

        retry_after = _seconds(headers.get("retry-after"))
        remaining = _seconds(headers.get("x-ratelimit-remaining"))
        reset = _seconds(headers.get("x-ratelimit-reset"))
        moment = time.time() if now is None else now
        delay = 0.0
        if retry_after is not None and status in {403, 429}:
            delay = retry_after
        elif remaining == 0 and reset is not None:
            delay = max(0.0, reset - moment)
        if delay > 0:
            self._pause_until = max(self._pause_until, self._clock() + delay)

    def set_listener(self, listener: Callable[[float], None] | None) -> None:
        """
        Report the remaining wait, in seconds, while a pause is in force.

        Args:
            listener: Called with the remaining delay, then with 0 when it ends.
                It must not await.

        """

        self._on_wait = listener

    async def wait(self) -> None:
        """Sleep when a previous response asked the client to slow down."""

        announced = False
        while True:
            async with self._lock:
                delay = self._pause_until - self._clock()
                if delay > 0 and not announced:
                    self.pauses += 1
                    announced = True
            if delay <= 0:
                if announced and self._on_wait is not None:
                    self._on_wait(0.0)
                return
            if self._on_wait is not None:
                self._on_wait(delay)
            await self._sleep(min(1.0, delay))


def _seconds(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
