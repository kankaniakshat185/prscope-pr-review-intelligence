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


def test_a_schedule_call_after_work_has_started_does_not_cancel_it():
    # Regression test: a new webhook event arriving while the previous
    # debounced run is already past its delay and mid-flight (e.g. an
    # in-progress repo-index refresh) must not cancel that in-flight work -
    # only a call that arrives *during the delay* should pre-empt it.
    async def _body():
        debouncer = WebhookDebouncer(delay_seconds=0.03)
        events = []

        async def slow_factory():
            events.append("first-started")
            await asyncio.sleep(0.1)  # stands in for in-flight work (e.g. an index build)
            events.append("first-finished")

        async def fast_factory():
            events.append("second-ran")

        debouncer.schedule("pr-1", slow_factory)
        await asyncio.sleep(0.05)  # past the delay - slow_factory is now running its "work"
        assert events == ["first-started"]

        debouncer.schedule("pr-1", fast_factory)  # must NOT cancel the in-flight first run
        await asyncio.sleep(0.2)  # long enough for both the second run's delay and the first's "work" to finish

        assert "first-finished" in events  # the in-flight run was allowed to complete
        assert "second-ran" in events  # the newer call still got its own run

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
