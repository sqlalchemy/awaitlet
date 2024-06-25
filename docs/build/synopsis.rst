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

The whole approach of awaitlet is overall a little bit of a "dark art" (though
actually less "dark" than what gevent and eventlet
have done for decades).  It
takes a standard and pretty well known part of Python, the ``asyncio``
library, and adds some syntactical helpers that were not intended to be part
of asyncio itself.   Inspired by libraries like gevent and eventlet, awaitlet
makes use of greenlet in a similar way as those libraries do, but then makes
use of asyncio for non-blocking primitives, rather than going through the
effort of creating its own and often needing to monkeypatch them into the standard
library the way gevent and eventlet do.

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

Above, the ``send_receive_logic()`` function is called within a greenlet that
itself links to a parent greenlet that's local to the :func:`.async_def`
callable (this is the normal way that greenlet works)::

    async def async_def(
        fn: Callable[..., _T],
        *args: Any,
        assert_await_occurs: bool = False,
        **kwargs: Any,
    ) -> _T:
        """Runs a sync function ``fn`` in a new greenlet."""

        # make a greenlet.greenlet with the given function.
        # getcurrent() is the parent greenlet that is basically where we
        # are right now in the function
        context = _AsyncIoGreenlet(fn, greenlet.getcurrent())

        # switch into the new greenlet (start the function)
        result = context.switch(*args, **kwargs)

        # ... continued ...

When this line of code is first called::

    # switch into the new greenlet (start the function)
    result = context.switch(*args, **kwargs)

It runs the given function, and blocks until the function is complete.
However, within the function (which is our ``send_receive_logic()`` call),
that function can call upon Python awaitables using :func:`.awaitlet`.
:func:`.awaitlet` looks like this::

    def awaitlet(awaitable: Awaitable[_T]) -> _T:
        """Awaits an async function in a sync method."""

        current = greenlet.getcurrent()
        return current.parent.switch(awaitable)

That is, it does nothing but context switch **back to the parent greenlet**,
which means back outside of the ``context.switch()`` that got us here.
The returned value is a real Python awaitable.  So inside
of the ``async_def()`` function, we check that the inner function is not
complete yet, we then assume the result must be an awaitable, and we await it
on behalf of our hosted function - remember, we're in a real ``async def``
at this level::

    # switch into the new greenlet (start the function)
    result = context.switch(*args, **kwargs)

    # loop for the function not done yet
    while not context.dead:
        # await on the result that we expect is awaitable
        value = await result

With the awaitable completed, we send the result of
the awaitable **back into the hosted function and context switch back**::

    # switch into the new greenlet (start the function)
    result = context.switch(*args, **kwargs)

    # loop for the function not done yet
    while not context.dead:
        # await on the result that we expect is awaitable
        value = await result

        # pass control back into the function, with the return value
        # of the awaitable
        result = context.switch(value)

The ``value`` passed in becomes the **return value of the awaitlet() call**::

    def awaitlet(awaitable: Awaitable[_T]) -> _T:
        # ...

        return current.parent.switch(awaitable)

and we are then back in the hosted function with an awaitable having proceeded
and its return value passed back from the :func:`.awaitlet` call.

The loop continues; each time ``context.dead`` is False, we know that
``result`` is yet another Python awaitable.   Once ``context.dead`` is
True, then we know the function completed; we return the result!

.. sourcecode::

    # switch into it (start the function)
    result = context.switch(*args, **kwargs)

    # loop for the function not done yet
    while not context.dead:
        # await on the result that we expect is awaitable
        value = await result

        result = context.switch(value)

    # no more awaits; so this is the result!
    return result


Minus error handling and some other robustness details, that's the whole thing!
