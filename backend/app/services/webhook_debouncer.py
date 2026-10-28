import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict


@dataclass
class _PendingRun:
    task: "asyncio.Task[None]"
    started: bool = False  # True once past the sleep and into coro_factory()


class WebhookDebouncer:
    """
    Coalesces rapid-fire events for the same key (e.g. several `synchronize`
    webhook events from a quick series of pushes to one PR) into a single
    run, instead of one run per event. Each new call for a key cancels that
    key's pending *timer* and restarts it - but only while it's still
    waiting; once a run has moved past the delay and started its real work
    (e.g. a repo-index refresh mid-flight), a new call lets it finish rather
    than cancelling it. `coro_factory()` work generally isn't written to
    expect being torn down by a cancellation at an arbitrary await point -
    repo_index_engine.build_or_update_index, for one, only transitions its
    RepoIndex row out of "indexing" from within a try/except that doesn't
    catch CancelledError, so a cancel mid-build left that row stuck in
    "indexing" forever (the webhook auto-refresh path only ever touches a
    repo index that's already "ready"). The new call instead gets its own
    independent timer/run for this key, so the newest push's data still
    gets its own fresh debounced run - it just doesn't abort the one
    already in progress to do it.

    In-memory and per-process, same tradeoff as rate_limiter.py: correct for
    a single backend instance, would need a shared store (e.g. Redis) behind
    multiple instances.
    """

    def __init__(self, delay_seconds: float):
        self.delay_seconds = delay_seconds
        self._pending: Dict[str, _PendingRun] = {}

    def schedule(self, key: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
        existing = self._pending.get(key)
        if existing is not None and not existing.task.done() and not existing.started:
            existing.task.cancel()

        pending = _PendingRun(task=None)  # type: ignore[arg-type]

        async def _run() -> None:
            try:
                await asyncio.sleep(self.delay_seconds)
            except asyncio.CancelledError:
                return
            pending.started = True
            try:
                await coro_factory()
            finally:
                # Only clear the slot if it's still *this* run - an even
                # newer schedule() call may have already replaced it.
                if self._pending.get(key) is pending:
                    self._pending.pop(key, None)

        pending.task = asyncio.create_task(_run())
        self._pending[key] = pending

    def pending_count(self) -> int:
        return len(self._pending)

    def reset(self) -> None:
        """Cancels and clears all pending timers. Exists for tests - this is
        process-global, in-memory state (same as rate_limiter.py), so a task
        scheduled in one test can otherwise leak into and interfere with the
        next one via a shared debounce key."""
        for pending in self._pending.values():
            if not pending.task.done():
                pending.task.cancel()
        self._pending.clear()
