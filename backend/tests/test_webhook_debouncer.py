import asyncio

from app.services.webhook_debouncer import WebhookDebouncer


def test_single_call_eventually_executes():
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.03)
        calls = []

        async def factory():
            calls.append("ran")

        debouncer.schedule("pr-1", factory)
        await asyncio.sleep(0.15)
        assert calls == ["ran"]
        assert debouncer.pending_count() == 0

    asyncio.run(_body())


def test_rapid_calls_for_the_same_key_only_run_the_latest():
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.05)
        calls = []

        async def make_factory(label):
            async def factory():
                calls.append(label)
            return factory

        debouncer.schedule("pr-1", await make_factory("first"))
        await asyncio.sleep(0.01)  # well within the debounce window
        debouncer.schedule("pr-1", await make_factory("second"))
        await asyncio.sleep(0.01)
        debouncer.schedule("pr-1", await make_factory("third"))

        await asyncio.sleep(0.15)  # let the window elapse
        assert calls == ["third"]

    asyncio.run(_body())


def test_the_cancelled_factory_is_never_actually_invoked():
    # Proves cancellation happens before the coroutine is even created, not
    # just before it finishes - schedule() takes a *factory* precisely so a
    # superseded call never produces a dangling unawaited coroutine.
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.05)
        invoked = []

        async def first_factory():
            invoked.append("first")

        async def second_factory():
            invoked.append("second")

        debouncer.schedule("pr-1", first_factory)
        await asyncio.sleep(0.01)
        debouncer.schedule("pr-1", second_factory)
        await asyncio.sleep(0.15)

        assert invoked == ["second"]

    asyncio.run(_body())


def test_different_keys_run_independently():
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.03)
        calls = []

        async def factory_a():
            calls.append("a")

        async def factory_b():
            calls.append("b")

        debouncer.schedule("pr-1", factory_a)
        debouncer.schedule("pr-2", factory_b)
        await asyncio.sleep(0.15)

        assert sorted(calls) == ["a", "b"]

    asyncio.run(_body())


def test_a_new_schedule_after_the_previous_run_completed_starts_fresh():
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.03)
        calls = []

        async def factory():
            calls.append("ran")

        debouncer.schedule("pr-1", factory)
        await asyncio.sleep(0.15)
        assert calls == ["ran"]

        debouncer.schedule("pr-1", factory)
        await asyncio.sleep(0.15)
        assert calls == ["ran", "ran"]

    asyncio.run(_body())
