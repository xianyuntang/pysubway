from __future__ import annotations

from asyncio import open_connection

from src.logger import logger
from src.stream import Message, MessageType, Stream, bridge, read, write


class Client:
    def __init__(
        self, *, control_host: str, control_port: str, local_port: str
    ) -> None:
        self.control_host = control_host
        self.control_port = control_port
        self.local_port = local_port

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

        await write(control_writer, message=Message(type=MessageType.hello))

        async for message in read(control_reader):
            logger.debug(f"Receive message: {message}")
            if message.type == MessageType.hello and message.endpoint is not None:
                logger.info(f"Server listens on {message.endpoint}")

            elif message.type == MessageType.close:
                logger.info("End connection")
                return

            elif message.type == MessageType.open and message.id is not None:
                logger.info(f"Receive request with id: {message.id}")
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
                    continue

                await write(
                    remote_writer,
                    message=Message(type=MessageType.accept, id=message.id),
                )
                await bridge(
                    Stream(reader=local_reader, writer=local_writer),
                    Stream(reader=remote_reader, writer=remote_writer),
                )
