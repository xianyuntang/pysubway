import asyncio
from asyncio import StreamReader, StreamWriter

from nanoid import generate

from src.logger import logger
from src.proxy import Proxy
from src.shared import (
    DEFAULT_DOMAIN,
    LOCAL_BIND,
    Message,
    MessageType,
    Stream,
    bridge,
    read,
    write,
)


class Server:
    def __init__(
        self, *, control_port: str, proxy_port: str, domain: str, use_ssl: bool
    ) -> None:
        self.control_port = control_port
        self.request_streams: dict[str, Stream] = {}

        self.proxy = Proxy(domain=domain, use_ssl=use_ssl, port=proxy_port)

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
        async for message in read(reader):
            logger.debug("Receive message: %s", message)
            if message.type == MessageType.hello:
                request_server = await asyncio.start_server(
                    lambda request_reader,
                    request_writer: self.handle_request_connection(
                        control_stream=Stream(reader=reader, writer=writer),
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
                subdomain = generate()
                endpoint = self.proxy.register_upstream(
                    subdomain=subdomain, port=request_server_port
                )
                logger.info(f"Request server listen on {request_server_port}")

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
                    await bridge(Stream(reader=reader, writer=writer), request_stream)
                    break

    async def handle_request_connection(
        self, control_stream: Stream, request_stream: Stream
    ) -> None:
        request_id = generate()
        logger.info("New connection id: %s", request_id)
        self.request_streams[request_id] = request_stream
        await write(
            control_stream.writer, message=Message(type=MessageType.open, id=request_id)
        )


if __name__ == "__main__":
    server = Server(
        control_port="5678", proxy_port="5679", domain=DEFAULT_DOMAIN, use_ssl=False
    )
    asyncio.run(server.listen())
