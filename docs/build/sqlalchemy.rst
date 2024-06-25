===================
Use with SQLAlchemy
===================

Awaitlet can be combined with code that uses SQLAlchemy in one or both of
two ways; one is by **using SQLAlchemy's asyncio API**, and the other is
**using SQLAlchemy's sync API with an asyncio driver**.

For the examples that follow, we'll make use of the following SQLAlchemy
ORM model::

    from __future__ import annotations

    import datetime
    from typing import Optional

    from sqlalchemy import ForeignKey
    from sqlalchemy import func
    from sqlalchemy import select
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import Mapped
    from sqlalchemy.orm import mapped_column


    class Base(DeclarativeBase):
        pass


    class A(Base):
        __tablename__ = "a"

        id: Mapped[int] = mapped_column(primary_key=True)
        data: Mapped[Optional[str]]
        create_date: Mapped[datetime.datetime] = mapped_column(
            server_default=func.now()
        )

Following the ORM model, we will also have a global async engine / session
setup, using the ``asyncpg`` PostgreSQL driver::

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine

    async_engine = create_async_engine(
        "postgresql+asyncpg://scott:tiger@localhost/test",
        echo=True,
    )
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)


Using SQLAlchemy's asyncio from non-async functions in asyncio programs
=======================================================================

If we have a program that makes use of SQLAlchemy asyncio, we can call upon
async defs which use this database logic from functions that are not themselves
declared as async.  Suppose our program had two async functions that
use SQLAlchemy's async API directly::

    async def setup_tables():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)


    async def work_with_data():
        async with async_session() as session:
            async with session.begin():
                session.add_all(
                    [
                        A(data="a1"),
                        A(data="a2"),
                        A(data="a3"),
                    ]
                )

            stmt = select(A.data)

            result = await session.scalars(stmt)
            return result.all()

(fun fact, the SQLAlchemy ``conn.run_sync()`` calls in the above example are
essentially equivalent to using awaitlet's :func:`.async_def` call)

If we had intermediary code that was not written to use asyncio, but wanted
to be able to call these functions directly when the overall program is run
in an asyncio context, we could achieve that as follows::

    import asyncio
    import awaitlet

    def call_async_db_code():
        awaitlet.awaitlet(setup_tables())
        result = awaitlet.awaitlet(work_with_data())
        return result

    async def front_facing_asyncio_facade():
        result = await awaitlet.async_def(call_async_db_code)
        print(f"Result: {result}")

    asyncio.run(front_facing_asyncio_facade())

Above, ``front_facing_asyncio_facade()`` represents code we've written to present
an asyncio front to our application.   ``call_async_db_code()`` represents some
part of the code that is written in traditional blocking style but has some
areas that want to call into async code.  The :func:`.async_def` function enters
the blocking function into an implicit async context, allowing the :func:`.awaitlet`
function to call out to real awaitables.


Using SQLAlchemy's sync API in Asyncio Programs
===============================================

In this pattern, we present the more compelling case of a large codebase that's
written to use SQLAlchemy's traditional blocking style API.   Given the above
methods written in blocking style::


    sessionmaker = sessionmaker(...)

    def setup_tables():
        with engine.begin() as conn:
            Base.metadata.drop_all(conn)
            Base.metadata.create_all(conn)


    def work_with_data():
        with sessionmaker() as session:
            with session.begin():
                session.add_all(
                    [
                        A(data="a1"),
                        A(data="a2"),
                        A(data="a3"),
                    ]
                )

            stmt = select(A.data)

            result = session.scalars(stmt)
            return result.all()

We'll note above the code is the same code as used previously, except we see
there is a traditional blocking style ``sessionmaker()`` in use.  The goal is
to run the above code against an asyncio database driver, in this case
asyncpg.   How can we achieve this?

Firstly, we continue to use the ``create_async_engine()`` call to create our
engine.  In SQLAlchemy, there is a blocking style ``Engine`` object embedded
in the ``AsyncEngine``, however it links to an asyncio driver and also modifies
some connection pool behaviors to be async compatible.   The accessibility of this ``Engine``
is part of SQLAlchemy's public async API.  So here, when we know our program
is using an asyncio driver, we create the engine as we did previously,
then link the ``Engine`` to our ``sessionmaker()``::

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker

    async_engine = create_async_engine(
        "postgresql+asyncpg://scott:tiger@localhost/test",
        echo=True,
    )

    sessionmaker = sessionmaker(async_engine.engine)

We can then call upon our ``setup_tables()`` and ``work_with_data()`` functions
**only** using :func:`.async_def`; SQLAlchemy itself will make use of its
internal form of :func:`.awaitlet` which is compatible with ours::

    import asyncio
    import awaitlet

    def call_async_db_code():
        setup_tables()
        result = work_with_data()
        return result

    async def front_facing_asyncio_facade():
        result = await awaitlet.async_def(call_async_db_code)
        print(f"Result: {result}")

    asyncio.run(front_facing_asyncio_facade())

Putting the program segments together we create a fully runnable example below::

    from __future__ import annotations

    import asyncio
    import datetime
    from typing import Optional

    import awaitlet
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import ForeignKey
    from sqlalchemy import func
    from sqlalchemy import select
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import Mapped
    from sqlalchemy.orm import mapped_column


    class Base(DeclarativeBase):
        pass


    class A(Base):
        __tablename__ = "a"

        id: Mapped[int] = mapped_column(primary_key=True)
        data: Mapped[Optional[str]]
        create_date: Mapped[datetime.datetime] = mapped_column(
            server_default=func.now()
        )


    async_engine = create_async_engine(
        "postgresql+asyncpg://scott:tiger@localhost/test",
        echo=True,
    )

    engine = async_engine.engine
    sessionmaker = sessionmaker(async_engine.engine)

    def setup_tables():
        with engine.begin() as conn:
            Base.metadata.drop_all(conn)
            Base.metadata.create_all(conn)


    def work_with_data():
        with sessionmaker() as session:
            with session.begin():
                session.add_all(
                    [
                        A(data="a1"),
                        A(data="a2"),
                        A(data="a3"),
                    ]
                )

            stmt = select(A.data)

            result = session.scalars(stmt)
            return result.all()

    def call_async_db_code():
        setup_tables()
        result = work_with_data()
        return result

    async def front_facing_asyncio_facade():
        result = await awaitlet.async_def(call_async_db_code)
        print(f"Result: {result}")

    asyncio.run(front_facing_asyncio_facade())

