import asyncio
from typing import Awaitable, Callable, Dict


class WebhookDebouncer:
    """
    Coalesces rapid-fire events for the same key (e.g. several `synchronize`
    webhook events from a quick series of pushes to one PR) into a single
    run, instead of one run per event. Each new call for a key cancels that
    key's pending timer and restarts it - only the last call within the
    delay window actually executes.

    In-memory and per-process, same tradeoff as rate_limiter.py: correct for
    a single backend instance, would need a shared store (e.g. Redis) behind
    multiple instances.
    """

    def __init__(self, delay_seconds: float):
        self.delay_seconds = delay_seconds
        self._pending: Dict[str, "asyncio.Task[None]"] = {}

    def schedule(self, key: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
        existing = self._pending.get(key)
        if existing is not None and not existing.done():
            existing.cancel()

        async def _run() -> None:
            try:
                await asyncio.sleep(self.delay_seconds)
                await coro_factory()
            except asyncio.CancelledError:
                pass
            finally:
                # Only clear the slot if it's still *this* task - an even
                # newer schedule() call may have already replaced it.
                if self._pending.get(key) is task:
                    self._pending.pop(key, None)

        task = asyncio.create_task(_run())
        self._pending[key] = task

    def pending_count(self) -> int:
        return len(self._pending)

    def reset(self) -> None:
        """Cancels and clears all pending timers. Exists for tests - this is
        process-global, in-memory state (same as rate_limiter.py), so a task
        scheduled in one test can otherwise leak into and interfere with the
        next one via a shared debounce key."""
        for task in self._pending.values():
            if not task.done():
                task.cancel()
        self._pending.clear()
