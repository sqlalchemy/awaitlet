========
Synopsis
========

This section will illustrate a very basic conversion of a threaded program
to use asyncio, while allowing non-async Python defs to coexist between
the front and backends.


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

With awaitlet, we dont have to.  awaitlet provides a **functional form
of the Python await call**, which can be invoked from non-async functions,
within an overall asyncio context.    We can port our program above by:

* Writing a new ``send_receive_implementation`` function that uses asyncio, rather than sync
* Writing a new ``send_receive_api`` that uses asyncio
* Writing a sync adapter that can be passed along to ``send_receive_logic``.
  This adapter will make use of the :func:`.awaitlet` function to ``await``
  an asyncio endpoint.  The adapter itself will be called within the
  :func:`.async_def` function so that it makes use of an implicit asyncio
  context.

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

Above, the front end and back end are ported to asyncio, but the middle part
stays the same; that is, the ``send_receive_logic()`` function **did not change
at all, no async/await keywords needed**.  That's the point of awaitlet; **to
eliminate the async/await keyword tax applied to code that doesnt directly
invoke non-blocking functions.**


Detailed Breakdown
==================

The whole approach of awaitlet is overall a little bit of a "dark art".   It
takes a standard and pretty well known part of Python, the ``asyncio``
library, and adds some syntactical helpers that were not intended to be part
of asyncio itself.   Inspired by libraries like gevent and eventlet, awaitlet
makes use of greenlet in a similar way as those libraries do, but then makes
use of asyncio for non-blocking primitives, rather than going through the
effort of creating its own the way gevent and eventlet do.

The :func:`.async_def` function call is an awaitable that when invoked,
internally starts up a greenlet that can be used to "context switch" to
other greenlets anywhere within the execution of that greenlet::

    async def some_function():
        my_awaitable = awaitlet.async_def(
            send_receive_logic,
            msg,
            "tcpbin.com",
            4242,
            adapt_async_implementation
        )

        return await my_awaitable

Above, the ``send_receive_logic()`` function is called within a greenlet, but
not before first before we enter into an actual async def that's behind
the scenes::

    async def async_def(
        fn: Callable[..., _T],
        *args: Any,
        assert_await_occurs: bool = False,
        **kwargs: Any,
    ) -> _T:
        """Runs a sync function ``fn`` in a new greenlet."""

        # make a greenlet.greenlet with the given function
        context = _AsyncIoGreenlet(fn, greenlet.getcurrent())

        # switch into it (start the function)
        result = context.switch(*args, **kwargs)

        # ... continued ...

Then, whenever some part of ``send_receive_logic()`` or some sub-function within
it calls upon :func:`.awaitlet`, that goes back into awaitlet's greenlet code
and uses ``greenlet.switch()`` to **context switch** back out into the behind-the-scenes
async function, below illustrated in a simplified form of the actual code::

    async def async_def(
        fn: Callable[..., _T],
        *args: Any,
        assert_await_occurs: bool = False,
        **kwargs: Any,
    ) -> _T:
        """Runs a sync function ``fn`` in a new greenlet."""

        # make a greenlet.greenlet with the given function
        context = _AsyncIoGreenlet(fn, greenlet.getcurrent())

        # switch into it (start the function)
        result = context.switch(*args, **kwargs)

        # we're back!  is the context not dead ? (e.g. the funciton has more
        # code to run?)
        while not context.dead:
            # wait for a coroutine from awaitlet and then return its
            # result back to it.
            value = await result

            # then switch back in!  (in reality there's error handling here also)
            result = context.switch(value)

When this line of code is first called::

    # switch into it (start the function)
    result = context.switch(*args, **kwargs)

It blocks while our function runs.   Only when our function exits or
calls :func:`.awaitlet` do we hit the next line.   If the function calls
:func:`.awaitlet`, awaitlet looks like this::

    def awaitlet(awaitable: Awaitable[_T]) -> _T:
        """Awaits an async function in a sync method."""

        current = greenlet.getcurrent()
        return current.parent.switch(awaitable)

That is, it does nothing but greenlet switch **back to the parent greenlet**,
which means back outside of the ``context.switch()`` that got us here.
The returned value is a real Python awaitable.  So inside
of the ``async_def()`` funciton, we await it on behalf of our hosted function::

    while not context.dead:
        # await on the result that we expect is awaitable
        value = await result

We send the result of the awaitable **back into the hosted function and
context switch back**::

    result = context.switch(value)

Minus some more robustness details, that's the whole thing!
