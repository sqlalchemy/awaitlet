from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Any
from typing import Coroutine
from typing import Literal
from typing import TypeVar
from typing import Union

from .typing import Self

_T = TypeVar("_T", bound=Any)


def eq_(a, b, msg=None):
    """Assert a == b, with repr messaging on failure."""
    assert a == b, msg or "%r != %r" % (a, b)


def ne_(a, b, msg=None):
    """Assert a != b, with repr messaging on failure."""
    assert a != b, msg or "%r == %r" % (a, b)


def run_coroutine_function(fn, *args, **kwargs):
    return _runner.run(fn(*args, **kwargs))


class _Runner:
    """Runner implementation for test only"""

    _loop: Union[None, asyncio.AbstractEventLoop, Literal[False]]

    def __init__(self) -> None:
        self._loop = None

    def __enter__(self) -> Self:
        self._lazy_init()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._loop:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            finally:
                self._loop.close()
                self._loop = False

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """Return embedded event loop."""
        self._lazy_init()
        assert self._loop
        return self._loop

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        self._lazy_init()
        assert self._loop
        return self._loop.run_until_complete(coro)

    def _lazy_init(self) -> None:
        if self._loop is False:
            raise RuntimeError("Runner is closed")
        if self._loop is None:
            self._loop = asyncio.new_event_loop()


_runner = _Runner()  # runner it lazy so it can be created here


async_test: Any = None  # assigned by conftest


class _ErrorContainer:
    error = None


@contextlib.contextmanager
def expect_raises(except_cls, check_context=True):
    ec = _ErrorContainer()
    if check_context:
        are_we_already_in_a_traceback = sys.exc_info()[0]
    try:
        yield ec
        success = False
    except except_cls as err:
        ec.error = err
        success = True
        if check_context and not are_we_already_in_a_traceback:
            _assert_proper_exception_context(err)
        print(str(err).encode("utf-8"))

    # it's generally a good idea to not carry traceback objects outside
    # of the except: block, but in this case especially we seem to have
    # hit some bug in either python 3.10.0b2 or greenlet or both which
    # this seems to fix:
    # https://github.com/python-greenlet/greenlet/issues/242
    del ec

    # assert outside the block so it works for AssertionError too !
    assert success, "Callable did not raise an exception"


def _assert_proper_exception_context(exception):
    """assert that any exception we're catching does not have a __context__
    without a __cause__, and that __suppress_context__ is never set.

    Python 3 will report nested as exceptions as "during the handling of
    error X, error Y occurred". That's not what we want to do.  we want
    these exceptions in a cause chain.

    """

    if (
        exception.__context__ is not exception.__cause__
        and not exception.__suppress_context__
    ):
        assert False, (
            "Exception %r was correctly raised but did not set a cause, "
            "within context %r as its cause."
            % (exception, exception.__context__)
        )
