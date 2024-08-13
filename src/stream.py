from __future__ import annotations

import contextlib
import json
from enum import StrEnum, auto
from typing import TYPE_CHECKING, AsyncGenerator

from anyio import create_task_group, sleep
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


async def _receive_or_timeout(stream: SocketStream, size: int = 65535) -> bytes | None:
    result: bytes | None = None

    with contextlib.suppress(Exception):
        async with create_task_group() as task_group:

            async def wrap_receive() -> bytes:
                nonlocal result
                result = await stream.receive(size)
                task_group.cancel_scope.cancel()
                return result

            async def wrap_sleep() -> None:
                await sleep(1)
                task_group.cancel_scope.cancel()

            task_group.start_soon(wrap_receive)
            task_group.start_soon(wrap_sleep)
    return result


async def _pipe(stream1: SocketStream, stream2: SocketStream) -> None:
    while True:
        data = await _receive_or_timeout(stream1)
        if not data:
            break
        await stream2.send(data)
    await stream2.aclose()


async def bridge(stream1: SocketStream, stream2: SocketStream) -> None:
    async with create_task_group() as task_group:
        task_group.start_soon(_pipe, stream1, stream2)
        task_group.start_soon(_pipe, stream2, stream1)


async def read(socket: SocketStream) -> AsyncGenerator[Message | None, None]:
    while True:
        length_data = await _receive_or_timeout(socket, 10)
        if length_data is None:
            yield None
            continue

        logger.debug(length_data)
        if not length_data:
            break
        message_length = int(length_data.decode().strip())

        message = ""
        while True:
            message_data = await _receive_or_timeout(socket, message_length)

            if message_data is None:
                yield None
                continue

            message = message_data.decode()
            logger.debug(message)
            break

        yield Message(**json.loads(message))


async def write(socket: SocketStream, *, message: Message) -> None:
    message_data = message.model_dump_json()
    message_body = message_data.encode()
    message_header = f"{len(message_body):>10}".encode()

    await socket.send(message_header + message_body)
    logger.debug("Send message %s", message_data)
