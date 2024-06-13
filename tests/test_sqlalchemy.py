import pytest

from awaitlet import async_def
from awaitlet.util.testing import async_test
from awaitlet.util.testing import eq_


try:
    import sqlalchemy
except ImportError:
    sqlalchemy = None
else:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from sqlalchemy import literal

requires_sqlalchemy = pytest.mark.skipif(
    sqlalchemy is None, reason="sqlalchemy not installed"
)


@requires_sqlalchemy
class TestSQLAlchemyIntegration:
    @async_test
    async def test_engine_excecute(self):
        ae = create_async_engine("sqlite+aiosqlite://")
        e = ae.sync_engine

        def do_stuff():
            with e.connect() as conn:
                data = conn.scalar(select(literal("hello")))

            return data

        data = await async_def(do_stuff)
        eq_(data, "hello")
