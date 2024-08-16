from __future__ import annotations

from anyio import connect_tcp, create_task_group

from src.logger import logger
from src.stream import Message, MessageType, bridge, read, write


class Client:
    def __init__(
        self, *, control_host: str, control_port: int, local_port: int, subdomain: str
    ) -> None:
        self.control_host = control_host
        self.control_port = control_port
        self.local_port = local_port
        self.subdomain = subdomain

    async def listen(self) -> None:
        try:
            control_stream = await connect_tcp(
                self.control_host, int(self.control_port)
            )
        except ConnectionRefusedError as e:
            logger.error(
                f"Failed to connect to {self.control_host}:{self.control_port} - {e}"
            )
            return

        await write(
            control_stream,
            message=Message(type=MessageType.hello, subdomain=self.subdomain),
        )

        async with create_task_group() as task_group:
            async for message in read(control_stream):
                logger.debug(f"Receive message: {message}")
                if message is None:
                    pass
                elif message.type == MessageType.hello and message.endpoint is not None:
                    logger.info(f"Server listens on {message.endpoint}")

                elif message.type == MessageType.close:
                    logger.info("End of connection")
                    return

                elif message.type == MessageType.open and message.id is not None:
                    logger.info(f"Receive request with id: {message.id}")

                    try:
                        remote_stream = await connect_tcp(
                            self.control_host, self.control_port
                        )

                        local_stream = await connect_tcp("127.0.0.1", self.local_port)
                    except OSError as e:
                        logger.error(e)
                        return

                    await write(
                        remote_stream,
                        Message(type=MessageType.accept, id=message.id),
                    )
                    task_group.start_soon(bridge, remote_stream, local_stream)
