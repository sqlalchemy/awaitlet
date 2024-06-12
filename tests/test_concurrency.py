import asyncio
import contextvars
import random

from awaitlet import async_def
from awaitlet import awaitlet
from awaitlet import NoAwaitletContext
from awaitlet import NoAwaitOccurred
from awaitlet.util.testing import async_test
from awaitlet.util.testing import eq_
from awaitlet.util.testing import expect_raises


async def run1():
    return 1


async def run2():
    return 2


def go(*fns):
    return sum(awaitlet(fn()) for fn in fns)


class TestAsyncioCompat:

    @async_test
    async def test_ok(self):
        eq_(await async_def(go, run1, run2), 3)

    @async_test
    async def test_async_error(self):
        async def err():
            raise ValueError("an error")

        with expect_raises(ValueError):
            await async_def(go, run1, err)

    @async_test
    async def test_propagate_cancelled(self):
        cleanup = []

        async def async_meth_raise():
            raise asyncio.CancelledError()

        def sync_meth():
            try:
                awaitlet(async_meth_raise())
            except:
                cleanup.append(True)
                raise

        async def run_w_cancel():
            await async_def(sync_meth)

        with expect_raises(asyncio.CancelledError, check_context=False):
            await run_w_cancel()

        assert cleanup

    @async_test
    async def test_sync_error(self):
        def go():
            awaitlet(run1())
            raise ValueError("sync error")

        with expect_raises(ValueError):
            await async_def(go)

    @async_test
    async def test_awaitletonly_no_greenlet(self):
        to_await = run1()
        with expect_raises(
            NoAwaitletContext,
        ):
            awaitlet(to_await)

        # existing awaitable is done
        with expect_raises(RuntimeError):
            await async_def(awaitlet, to_await)

        # no warning for a new one...
        to_await = run1()
        await async_def(awaitlet, to_await)

    @async_test
    async def test_awaitletonly_error(self):
        to_await = run1()

        await to_await

        async def inner_await():
            nonlocal to_await
            to_await = run1()
            awaitlet(to_await)

        def go():
            awaitlet(inner_await())

        with expect_raises(NoAwaitletContext):
            await async_def(go)

        with expect_raises(RuntimeError):
            await to_await

    @async_test
    async def test_contextvars(self):
        var = contextvars.ContextVar("var")
        concurrency = 500

        # NOTE: sleep here is not necessary. It's used to simulate IO
        # ensuring that task are not run sequentially
        async def async_inner(val):
            await asyncio.sleep(random.uniform(0.005, 0.015))
            eq_(val, var.get())
            return var.get()

        async def async_set(val):
            await asyncio.sleep(random.uniform(0.005, 0.015))
            var.set(val)

        def inner(val):
            retval = awaitlet(async_inner(val))
            eq_(val, var.get())
            eq_(retval, val)

            # set the value in a sync function
            newval = val + concurrency
            var.set(newval)
            syncset = awaitlet(async_inner(newval))
            eq_(newval, var.get())
            eq_(syncset, newval)

            # set the value in an async function
            retval = val + 2 * concurrency
            awaitlet(async_set(retval))
            eq_(var.get(), retval)
            eq_(awaitlet(async_inner(retval)), retval)

            return retval

        async def task(val):
            await asyncio.sleep(random.uniform(0.005, 0.015))
            var.set(val)
            await asyncio.sleep(random.uniform(0.005, 0.015))
            return await async_def(inner, val)

        values = {
            await coro
            for coro in asyncio.as_completed(
                [task(i) for i in range(concurrency)]
            )
        }
        eq_(values, set(range(concurrency * 2, concurrency * 3)))

    @async_test
    async def test_require_await(self):
        def run():
            return 1 + 1

        assert (await async_def(run)) == 2

        with expect_raises(
            NoAwaitOccurred,
        ):
            await async_def(run, assert_await_occurs=True)
