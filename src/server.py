from typing import TYPE_CHECKING

from anyio import create_task_group, create_tcp_listener
from anyio.abc import SocketAttribute, SocketStream
from nanoid import generate

from src.const import LOCAL_BIND
from src.logger import logger
from src.proxy import Proxy
from src.stream import (
    Message,
    MessageType,
    bridge,
    read,
    write,
)

if TYPE_CHECKING:
    from anyio.streams.stapled import MultiListener


class Server:
    def __init__(self, *, control_port: str, domain: str, use_ssl: bool) -> None:
        self.control_port = control_port
        self.request_streams: dict[str, SocketStream] = {}  # [id, SocketStream]
        self.request_servers: dict[
            int, MultiListener[SocketStream]
        ] = {}  # [port, MultiListener[SocketStream]]
        self.control_streams: dict[int, SocketStream] = {}  # [port, SocketStream]

        self.proxy = Proxy(
            domain=domain, use_ssl=use_ssl, end_connection=self.end_connection
        )

    async def end_connection(self, port: int) -> None:
        request_server = self.request_servers.pop(port)
        control_stream = self.control_streams.pop(port)
        if request_server:
            await write(
                control_stream,
                message=Message(type=MessageType.close),
            )
            await request_server.aclose()
            await control_stream.aclose()

    async def listen(self) -> None:
        control_server = await create_tcp_listener(
            local_host=LOCAL_BIND, local_port=int(self.control_port)
        )

        logger.info(f"Control server listen on {LOCAL_BIND}:{self.control_port}")
        async with create_task_group() as task_group:
            task_group.start_soon(control_server.serve, self.handle_connection)
            task_group.start_soon(self.proxy.listen)

    async def handle_connection(self, control_stream: SocketStream) -> None:
        async for message in read(control_stream):
            logger.debug("Receive message: %s", message)
            if message.type == MessageType.hello:
                request_server = await create_tcp_listener(local_host=LOCAL_BIND)

                request_server_port: int = int(
                    request_server.listeners[0].extra(SocketAttribute.local_address)[1]
                )

                endpoint = self.proxy.register_upstream(port=request_server_port)
                logger.info(
                    f"Request server listen on http://{LOCAL_BIND}:{request_server_port}"
                )

                self.request_servers[request_server_port] = request_server
                self.control_streams[request_server_port] = control_stream

                await write(
                    control_stream,
                    message=Message(
                        type=MessageType.hello,
                        endpoint=endpoint,
                    ),
                )

                await request_server.serve(
                    lambda rs: self.handle_request_connection(
                        control_stream=control_stream, request_stream=rs
                    )
                )

            elif message.type == MessageType.accept and message.id is not None:
                request_stream = self.request_streams.pop(message.id)
                if request_stream:
                    await bridge(request_stream, control_stream)
                    break

    async def handle_request_connection(
        self, control_stream: SocketStream, request_stream: SocketStream
    ) -> None:
        request_id = generate()
        logger.info("Receive request with id: %s", request_id)
        self.request_streams[request_id] = request_stream
        await write(
            control_stream, message=Message(type=MessageType.open, id=request_id)
        )
