from __future__ import annotations

import asyncio
from asyncio import open_connection

from src.shared import MessageType, Stream, logger, proxy, read, write


class Client:
    def __init__(
        self, *, control_host: str, control_port: str, local_port: str
    ) -> None:
        self.control_host = control_host
        self.control_port = control_port
        self.local_port = local_port

        self.control_stream: Stream | None = None
        self.remote_port: str | None = None

    async def listen(self) -> None:
        control_reader, control_writer = await open_connection(
            self.control_host, self.control_port
        )
        self.control_stream = Stream(reader=control_reader, writer=control_writer)

        await write(control_writer, message_type=MessageType.hello)
        async for message in read(control_reader):
            logger.debug(f"Receive message: {message}")
            if message["message_type"] == MessageType.hello:
                logger.info(f'Server listens on {message["port"]}')
                self.remote_port = message["port"]

            elif message["message_type"] == MessageType.connection:
                remote_reader, remote_writer = await open_connection(
                    self.control_host, self.control_port
                )
                local_reader, local_writer = await open_connection(
                    "127.0.0.1", self.local_port
                )

                await write(
                    remote_writer, message_type=MessageType.accept, id=message["id"]
                )
                await proxy(
                    Stream(reader=remote_reader, writer=remote_writer),
                    Stream(reader=local_reader, writer=local_writer),
                )


if __name__ == "__main__":
    client = Client(control_host="0.0.0.0", control_port="7835", local_port="4200")  # noqa: S104
    asyncio.run(client.listen())
