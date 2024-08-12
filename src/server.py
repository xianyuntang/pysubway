import asyncio
from asyncio import Server as _Server
from asyncio import StreamReader, StreamWriter

from nanoid import generate

from src.const import LOCAL_BIND
from src.logger import logger
from src.proxy import Proxy
from src.stream import (
    Message,
    MessageType,
    Stream,
    bridge,
    close_stream,
    read,
    write,
)


class Server:
    def __init__(self, *, control_port: str, domain: str, use_ssl: bool) -> None:
        self.control_port = control_port
        self.request_streams: dict[str, Stream] = {}  # [id, Stream]
        self.request_servers: dict[str, _Server] = {}  # [port, Server]
        self.control_streams: dict[str, Stream] = {}  # [port, Server]

        self.proxy = Proxy(
            domain=domain, use_ssl=use_ssl, end_connection=self.end_connection
        )

    async def end_connection(self, port: str) -> None:
        request_server = self.request_servers.pop(port)
        control_stream = self.control_streams.pop(port)
        if request_server:
            await write(
                writer=control_stream.writer,
                message=Message(type=MessageType.close),
            )
            request_server.close()
            await close_stream(control_stream.writer)

    async def listen(self) -> None:
        control_server = await asyncio.start_server(
            self.handle_connection, LOCAL_BIND, self.control_port
        )

        async with control_server:
            logger.info(f"Control server listen on {LOCAL_BIND}:{self.control_port}")
            await asyncio.gather(control_server.start_serving(), self.proxy.listen())

    async def handle_connection(
        self, reader: StreamReader, writer: StreamWriter
    ) -> None:
        control_stream = Stream(reader=reader, writer=writer)
        async for message in read(reader):
            logger.debug("Receive message: %s", message)
            if message.type == MessageType.hello:
                request_server = await asyncio.start_server(
                    lambda request_reader,
                    request_writer: self.handle_request_connection(
                        control_stream=control_stream,
                        request_stream=Stream(
                            reader=request_reader, writer=request_writer
                        ),
                    ),
                    LOCAL_BIND,
                    0,
                )

                request_server_port: str = str(
                    request_server.sockets[0].getsockname()[1]
                )

                endpoint = self.proxy.register_upstream(port=request_server_port)
                logger.info(f"Request server listen on {request_server_port}")

                self.request_servers[request_server_port] = request_server
                self.control_streams[request_server_port] = control_stream

                await write(
                    writer,
                    message=Message(
                        type=MessageType.hello,
                        endpoint=endpoint,
                    ),
                )
                async with request_server:
                    await request_server.serve_forever()
            elif message.type == MessageType.accept and message.id is not None:
                request_stream = self.request_streams.pop(message.id)
                if request_stream:
                    await bridge(request_stream, control_stream)
                    break

    async def handle_request_connection(
        self, control_stream: Stream, request_stream: Stream
    ) -> None:
        request_id = generate()
        logger.info("Receive request with id: %s", request_id)
        self.request_streams[request_id] = request_stream
        await write(
            control_stream.writer, message=Message(type=MessageType.open, id=request_id)
        )
