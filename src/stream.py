from __future__ import annotations

import json
from enum import StrEnum, auto
from typing import TYPE_CHECKING, AsyncGenerator

from anyio import (
    BrokenResourceError,
    ClosedResourceError,
    EndOfStream,
    connect_tcp,
    create_task_group,
)
from pydantic import BaseModel

from src.logger import logger

if TYPE_CHECKING:
    from anyio.abc import SocketStream


class MessageType(StrEnum):
    hello = auto()
    open = auto()
    accept = auto()
    close = auto()


class Message(BaseModel):
    type: MessageType
    id: str | None = None
    endpoint: str | None = None
    subdomain: str | None = None


async def _pipe(stream1: SocketStream, stream2: SocketStream) -> None:
    try:
        while True:
            data = await stream1.receive()
            if not data:
                break
            await stream2.send(data)
    except (ClosedResourceError, BrokenResourceError, EndOfStream):
        await stream2.aclose()


async def bridge(stream1: SocketStream, stream2: SocketStream) -> None:
    async with create_task_group() as task_group:
        task_group.start_soon(_pipe, stream1, stream2)
        task_group.start_soon(_pipe, stream2, stream1)


async def read(socket: SocketStream) -> AsyncGenerator[Message | None, None]:
    try:
        while True:
            length_data = await socket.receive(10)
            if not length_data:
                break
            message_length = int(length_data.decode().strip())

            message_data = await socket.receive(message_length)
            if not message_data:
                break

            message = message_data.decode()
            logger.debug(message)

            yield Message(**json.loads(message))
    except EndOfStream:
        logger.debug("End of connection")


async def write(socket: SocketStream, message: Message) -> None:
    message_data = message.model_dump_json()
    message_body = message_data.encode()
    message_header = f"{len(message_body):>10}".encode()

    await socket.send(message_header + message_body)
    logger.debug("Send message %s", message_data)


async def is_tcp_open(host: str, port: int) -> bool:
    try:
        stream = await connect_tcp(host, port)
        await stream.aclose()
    except OSError:
        return False
    else:
        return True
