========
awaitlet
========

Call Python asyncio awaitables from functions that are not declared
as async.

Synopsis
========

Consider the following asyncio program that sends and receives messages
from an echo server::

    import asyncio

    async def sendrecv(msg):
        reader, writer = await asyncio.open_connection("tcpbin.com", 4242)
        writer.write(f"message number {msg}\n".encode("ascii"))
        await writer.drain()
        data = (await reader.read(1024)).decode("utf-8")
        return data


    async def main():
        messages = await asyncio.gather(
            *[
                sendrecv(msg) for msg in
                ["one", "two", "three", "four", "five"]
            ]
        )
        for msg in messages:
            print(f"Got back echo response: {msg}")

    asyncio.run(main())

What if ``sendrecv`` above wanted to be a function available in existing
code that didn't use ``async``?   With awaitlet we can remove the ``async``
keyword and still have a way of invoking ``async`` awaitables inside
of it::


    import asyncio
    from awaitlet import async_def
    from awaitlet import awaitlet

    def sendrecv_implementation(msg):
        reader, writer = awaitlet(asyncio.open_connection("tcpbin.com", 4242))
        writer.write(f"message number {msg}\n".encode("ascii"))
        awaitlet(writer.drain())
        data = (awaitlet(reader.read(1024))).decode("utf-8")
        return data

    async def sendrecv(msg):
        return await async_def(sendrecv_implementation, msg)

    async def main():
        messages = await asyncio.gather(
            *[
                sendrecv(msg) for msg in
                ["one", "two", "three", "four", "five"]
            ]
        )
        for msg in messages:
            print(f"Got back echo response: {msg}")

    asyncio.run(main())



