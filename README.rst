========
awaitlet
========

Allow non-async defs that invoke awaitables inside of asyncio applications.

awaitlet allows existing programs written to use threads and blocking
APIs to be ported to asyncio, by replacing frontend and backend code with
asyncio compatible approaches, but allowing intermediary code to remain
completely unchanged.  Its primary use is to support code that is cross-compatible
with asyncio and non-asyncio runtime environments.

The entire API demonstrated in three lines, where a non ``async`` def can
be invoked in an asyncio context and can then call upon real awaitables
directly::

    import asyncio

    import awaitlet

    def asyncio_sleep():
        return awaitlet.awaitlet(asyncio.sleep(5, result='hello'))

    print(asyncio.run(awaitlet.async_def(asyncio_sleep)))

awaitlet is spun out from SQLAlchemy's own `asyncio mediation layer
<https://docs.sqlalchemy.org/en/latest/orm/extensions/asyncio.html>`_, with no
dependencies on SQLAlchemy itself.  awaitlet may be compared with another
equivalent library `greenback <https://pypi.org/project/greenback/>`_ which was
released at roughly the same time as SQLAlchemy's asyncio API.

awaitlet is intentionally fully compatible with SQLAlchemy's asyncio mediation
layer, and includes API patterns for:

* Converting any threaded program (no SQLAlchemy dependency necessary) to use
  asyncio patterns for front facing APIs and backends, without modifying
  intermediary code
* Converting threaded database-enabled programs to use asyncio patterns for
  front facing APIs and backends, where those backends use SQLAlchemy's asyncio
  API for database access
* Converting threaded database-enabled programs to use asyncio patterns for
  front facing APIs and backends, without modifying intermediary code that uses
  SQLAlchemy's synchronous API for database access

Documentation for awaitlet is within this source distribution and availble on
the web at https://awaitlet.sqlalchemy.org .

