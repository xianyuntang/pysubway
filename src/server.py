import asyncio
from asyncio import StreamReader, StreamWriter
from uuid import uuid4

from src.shared import MessageType, Stream, logger, proxy, read, write

CONTROL_HOST = "0.0.0.0"  # noqa: S104


class Server:
    def __init__(self, *, control_port: str) -> None:
        self.control_port = control_port
        self.request_streams: dict[str, Stream] = {}

    async def listen(self) -> None:
        control_server = await asyncio.start_server(
            self.handle_connection, CONTROL_HOST, self.control_port
        )

        async with control_server:
            logger.info(f"Start listen on port {self.control_port}")
            await control_server.serve_forever()

    async def handle_connection(
        self, reader: StreamReader, writer: StreamWriter
    ) -> None:
        async for message in read(reader):
            logger.debug("Receive message: %s", message)
            if message["message_type"] == MessageType.hello:
                logger.info("Accept client hello")

                request_server = await asyncio.start_server(
                    lambda request_reader,
                    request_writer: self.handle_request_connection(
                        control_stream=Stream(reader=reader, writer=writer),
                        request_stream=Stream(
                            reader=request_reader, writer=request_writer
                        ),
                    ),
                    CONTROL_HOST,
                    0,
                )
                request_server_port = request_server.sockets[0].getsockname()[1]
                await write(
                    writer,
                    message_type=MessageType.hello,
                    port=request_server_port,
                )
                async with request_server:
                    await request_server.serve_forever()
            elif message["message_type"] == MessageType.accept:
                request_stream = self.request_streams.pop(message["id"])
                if request_stream:
                    await proxy(Stream(reader=reader, writer=writer), request_stream)
                    break

    async def handle_request_connection(
        self, control_stream: Stream, request_stream: Stream
    ) -> None:
        request_id = str(uuid4())
        logger.info("New connection id: %s", request_id)
        self.request_streams[request_id] = request_stream
        await write(
            control_stream.writer,
            message_type=MessageType.open,
            id=request_id,
        )


if __name__ == "__main__":
    server = Server(control_port="5678")
    asyncio.run(server.listen())
