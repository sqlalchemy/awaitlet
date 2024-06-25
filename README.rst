========
awaitlet
========

Allow non-async defs that invoke awaitables inside of asyncio applications.

awaitlet allows existing programs written to use threads and blocking
APIs to be ported to asyncio, by replacing frontend and backend code with
asyncio compatible approaches, but allowing intermediary code to remain
completely unchanged.  Its primary use is to support code that is cross-compatible
with asyncio and non-asyncio runtime environments.

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

