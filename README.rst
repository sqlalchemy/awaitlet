========
awaitlet
========

Allow non-async defs that invoke awaitables inside of asyncio applications.

awaitlet allows existing programs written to use threads and blocking
APIs to be ported to asyncio, by replacing frontend and backend code with
asyncio compatible approaches, but allowing intermediary code to remain
completely unchanged.  Its primary use is to support code that is cross-compatible
with asyncio and non-asyncio runtime environments.


Synopsis
========

Consider the following multithreaded program, which sends and receives messages
from an echo server.  The program is organized into three layers:

* ``send_receive_implementation`` - this is a low level layer that interacts
  with the Python ``socket`` library directly

* ``send_receive_logic`` - this is logic code that responds to requests to
  send and receive messages, given an implementation function

* ``send_receive_api`` - this is the front-facing API that is used by programs.

We present this example below, adding a ``main()`` function that spins up
five threads and calls upon ``send_receive_api()`` independently within each:

.. sourcecode:: python

    import socket
    import threading

    messages = []

    def send_receive_implementation(host, port, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.sendall(message.encode("ascii"))
        return sock.recv(1024).decode("utf-8")

    def send_receive_logic(msg, host, port, implementation):
        return implementation(host, port, f"message number {msg}\n")

    def send_receive_api(msg):
        messages.append(
            send_receive_logic(msg, "tcpbin.com", 4242, send_receive_implementation)
        )

    def main():
        threads = [
            threading.Thread(target=send_receive_api, args=(msg,))
            for msg in ["one", "two", "three", "four", "five"]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for msg in messages:
            print(f"Got back echo response: {msg}")


    main()

The goal we have now is to provide an all-new asynchronous API to this program.
That is, we want to remove the use of threads, and instead have calling code which
looks like this:

.. sourcecode:: python

    async def main():
        messages = await asyncio.gather(
            *[
                message_api(msg) for msg in
                ["one", "two", "three", "four", "five"]
            ]
        )
        for msg in messages:
            print(f"Got back echo response: {msg}")

    asyncio.run(main())

To do this, we would need to rewrite all of the above functions to use
``async`` and ``await``.   But what if the vast majority of our code were
within ``send_receive_logic()`` - that code is only a pass through, receiving
data to and from an opaque implementation.  Must we convert **all** our code
everywhere that acts as "pass through" to use ``async`` ``await``?

With awaitlet, we dont have to.   awaitlet provides a **functional form
of the Python await call**, which can be invoked from non-async functions,
within an overall asyncio context.    We can port our program above by:

* Writing a new ``send_receive_implementation`` function that uses asyncio, rather than sync
* Writing a new ``send_receive_api`` that uses asyncio
* Writing a sync adapter that can be passed along to ``send_receive_logic``

This program then looks like:

.. sourcecode:: python

    import asyncio
    import awaitlet


    async def async_send_receive_implementation(host, port, message):
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(message.encode("ascii"))
        await writer.drain()
        data = (await reader.read(1024)).decode("utf-8")
        return data


    def send_receive_logic(msg, host, port, implementation):
        return implementation(host, port, f"message number {msg}\n")

    async def send_receive_api(msg):
        def adapt_async_implementation(host, port, message):
            return awaitlet.awaitlet(
                async_send_receive_implementation(host, port, message)
            )

        return await awaitlet.async_def(
            send_receive_logic,
            msg,
            "tcpbin.com",
            4242,
            adapt_async_implementation
        )

    async def main():
        messages = await asyncio.gather(
            *[
                send_receive_api(msg)
                for msg in ["one", "two", "three", "four", "five"]
            ]
        )
        for msg in messages:
            print(f"Got back echo response: {msg}")


    asyncio.run(main())

Above, the front end and back end are ported to asyncio, but the
middle part stays the same; that is, the ``send_receive_logic()`` function 
**did not change at all, no async/await keywords needed**.  That's the point of awaitlet; **to eliminate
the async/await keyword tax applied to code that doesnt directly invoke
non-blocking functions.**

How does this work?
===================

The context shift feature of the Python ``await`` keyword is made available in a functional 
way using the `greenlet <https://pypi.org/project/greenlet/>`_ library.  The source code for 
``async_def()`` and ``awaitlet()`` are a only a few dozen lines of code, using greenlet
to adapt ``awaitlet()`` function calls to real Python ``await`` keywords.

Has anyone used this before?
============================

Are you using `SQLAlchemy with asyncio <https://docs.sqlalchemy.org/en/latest/orm/extensions/asyncio.html>`_ anywhere?   Then **you're using it right now**.
awaitlet is a port of SQLAlchemy's own greenlet/asyncio mediation layer pulled into its own package, with no
dependencies on SQLAlchemy.   This code has been in widespread production use in thousands of environments for several
years, starting in 2020 with SQLAlchemy 1.4's first release.

