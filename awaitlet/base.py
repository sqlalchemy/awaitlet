from __future__ import annotations

import asyncio
import sys
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Coroutine
from typing import TYPE_CHECKING
from typing import TypeGuard
from typing import TypeVar

from greenlet import greenlet

_T = TypeVar("_T")


def is_exit_exception(e: BaseException) -> bool:
    # note asyncio.CancelledError is already BaseException
    # so was an exit exception in any case
    return not isinstance(e, Exception) or isinstance(
        e, (asyncio.TimeoutError, asyncio.CancelledError)
    )


class NoAwaitletContext(Exception):
    pass


class NoAwaitOccurred(Exception):
    pass


class _AsyncIoGreenlet(greenlet):
    dead: bool

    __sqlalchemy_greenlet_provider__ = True

    def __init__(self, fn: Callable[..., Any], driver: greenlet):
        greenlet.__init__(self, fn, driver)
        self.gr_context = driver.gr_context


if TYPE_CHECKING:
    _T_co = TypeVar("_T_co", covariant=True)

    def iscoroutine(
        awaitable: Awaitable[_T_co],
    ) -> TypeGuard[Coroutine[Any, Any, _T_co]]: ...

else:
    iscoroutine = asyncio.iscoroutine


def _safe_cancel_awaitable(awaitable: Awaitable[Any]) -> None:
    # https://docs.python.org/3/reference/datamodel.html#coroutine.close

    if iscoroutine(awaitable):
        awaitable.close()


def awaitlet(awaitable: Awaitable[_T]) -> _T:
    """Awaits an async function in a sync method.

    The sync method must be inside a :func:`greenlet_spawn` context.
    :func:`await_` calls cannot be nested.

    :param awaitable: The coroutine to call.

    """
    # this is called in the context greenlet while running fn
    current = greenlet.getcurrent()
    if not getattr(current, "__sqlalchemy_greenlet_provider__", False):
        _safe_cancel_awaitable(awaitable)

        raise NoAwaitletContext(
            "Can't call awaitlet() unless the call stack was invoked with "
            "async_def()."
        )

    # returns the control to the driver greenlet passing it
    # a coroutine to run. Once the awaitable is done, the driver greenlet
    # switches back to this greenlet with the result of awaitable that is
    # then returned to the caller (or raised as error)
    return current.parent.switch(awaitable)  # type: ignore[no-any-return]


async def async_def(
    fn: Callable[..., _T],
    *args: Any,
    assert_await_occurs: bool = False,
    **kwargs: Any,
) -> _T:
    """Runs a sync function ``fn`` in a new greenlet.

    The sync function can then use :func:`await_` to wait for async
    functions.

    :param fn: The sync callable to call.
    :param \\*args: Positional arguments to pass to the ``fn`` callable.
    :param \\*\\*kwargs: Keyword arguments to pass to the ``fn`` callable.
    """

    result: Any
    context = _AsyncIoGreenlet(fn, greenlet.getcurrent())
    # runs the function synchronously in gl greenlet. If the execution
    # is interrupted by await_, context is not dead and result is a
    # coroutine to wait. If the context is dead the function has
    # returned, and its result can be returned.
    switch_occurred = False
    result = context.switch(*args, **kwargs)
    while not context.dead:
        switch_occurred = True
        try:
            # wait for a coroutine from await_ and then return its
            # result back to it.
            value = await result
        except BaseException:
            # this allows an exception to be raised within
            # the moderated greenlet so that it can continue
            # its expected flow.
            result = context.throw(*sys.exc_info())
        else:
            result = context.switch(value)

    if assert_await_occurs and not switch_occurred:
        raise NoAwaitOccurred("Function was run but no await was called.")
    return result  # type: ignore[no-any-return]
