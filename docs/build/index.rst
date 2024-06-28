==========================================
Welcome to awaitlet's documentation!
==========================================


Awaitlet allows non-async defs that invoke awaitables inside of asyncio applications.

awaitlet allows existing programs written to use threads and blocking APIs to
be ported to asyncio, by replacing frontend and backend code with asyncio
compatible approaches, but allowing intermediary code to remain completely
unchanged, with no addition of ``async`` or ``await`` keywords throughout the
entire codebase needed.  Its primary use is to support code that is
cross-compatible with asyncio and non-asyncio runtime environments.

Awaitlet is a direct extract of SQLAlchemy's own `asyncio mediation layer
<https://docs.sqlalchemy.org/en/latest/orm/extensions/asyncio.html>`_, with no
dependencies on SQLAlchemy (but is also fully cross-compatible with
SQLAlchemy's mediation layer).   This code has been in widespread production
use in thousands of environments for several years, starting in 2020 with
SQLAlchemy 1.4's first release.     The library provides for the identical use
case as another library that was first released around the same time as
SQLAlchemy 1.4 called `greenback <https://pypi.org/project/greenback/>`_, but
as part of the SQLAlchemy project is guaranteed to remain cross-compatible with
non-blocking SQLAlchemy code.

awaitlet without any dependency or use of SQLAlchemy includes API patterns for:

* Converting any threaded program (no SQLAlchemy dependency necessary) to use
  asyncio patterns for front facing APIs and backends, without modifying
  intermediary code

For applications that do use SQLAlchemy, awaitlet provides additional
API patterns for:

* Converting threaded database-enabled programs to use asyncio patterns for
  front facing APIs and backends, where those backends use SQLAlchemy's asyncio
  API for database access
* Converting threaded database-enabled programs to use asyncio patterns for
  front facing APIs and backends, without modifying intermediary code that uses
  SQLAlchemy's synchronous API for database access

The two functions provided are :func:`.async_def` and :func:`.awaitlet`.  Using
these, we can create an asyncio program using intermediary defs that do not use the ``async``
or ``await`` keywords, but instead use functions::

   import asyncio

   import awaitlet

   def asyncio_sleep():
       return awaitlet.awaitlet(asyncio.sleep(5, result='hello'))

   print(asyncio.run(awaitlet.async_def(asyncio_sleep)))

Above, the ``asyncio_sleep()`` def is run directly in asyncio and calls upon
the ``asyncio.sleep()`` async API call, but the function itself does not declare
itself as ``async``; instead, this is applied functionally using the
:func:`.async_def` function.   Through this approach, a program can be made
to use asyncio for its front-facing API, talking to asyncio libraries for
non-blocking IO patterns, while not impacting intermediary code, which remains
compatible with non-asyncio use as well.

For a more complete example see :doc:`synopsis`.


How does this work?
===================

The context shift feature of the Python ``await`` keyword is made available in a functional
way using the `greenlet <https://pypi.org/project/greenlet/>`_ library.  The source code for
:func:`.async_def` and :func:`.awaitlet` are a only a few dozen lines of code, using greenlet
to adapt :func:`.awaitlet` function calls to real Python ``await`` keywords.


Contents in this Document
==========================

.. toctree::
   :maxdepth: 2

   front
   synopsis
   sqlalchemy
   api
   changelog




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

