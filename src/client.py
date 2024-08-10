from __future__ import annotations

import asyncio
from asyncio import open_connection

import uvloop

from src.logger import logger
from src.shared import Message, MessageType, Stream, bridge, read, write

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Client:
    def __init__(
        self, *, control_host: str, control_port: str, local_port: str
    ) -> None:
        self.control_host = control_host
        self.control_port = control_port
        self.local_port = local_port

        self.control_stream: Stream | None = None

    async def listen(self) -> None:
        try:
            control_reader, control_writer = await open_connection(
                self.control_host, self.control_port
            )
        except ConnectionRefusedError as e:
            logger.error(
                f"Failed to connect to {self.control_host}:{self.control_port} - {e}"
            )
            return

        self.control_stream = Stream(reader=control_reader, writer=control_writer)

        await write(control_writer, message=Message(type=MessageType.hello))

        async for message in read(control_reader):
            logger.debug(f"Receive message: {message}")
            if message.type == MessageType.hello and message.endpoint is not None:
                logger.info(f"Server listens on {message.endpoint}")

            elif message.type == MessageType.open and message.id is not None:
                try:
                    remote_reader, remote_writer = await open_connection(
                        self.control_host, self.control_port
                    )
                except ConnectionRefusedError as e:
                    logger.error(
                        f"Failed to connect to {self.control_host}:{self.control_port}"
                        f" - {e}"
                    )
                    return
                try:
                    local_reader, local_writer = await open_connection(
                        "127.0.0.1", self.local_port
                    )
                except ConnectionRefusedError as e:
                    logger.error(
                        f"Failed to connect to 127.0.0.1:{self.local_port} - {e}"
                    )
                    return

                await write(
                    remote_writer,
                    message=Message(type=MessageType.accept, id=message.id),
                )
                await bridge(
                    Stream(reader=remote_reader, writer=remote_writer),
                    Stream(reader=local_reader, writer=local_writer),
                )


if __name__ == "__main__":
    client = Client(control_host="0.0.0.0", control_port="5678", local_port="4200")  # noqa: S104
    asyncio.run(client.listen())
