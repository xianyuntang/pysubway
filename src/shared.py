from __future__ import annotations

import asyncio
import json
import logging
from asyncio import StreamReader, StreamWriter
from enum import StrEnum, auto
from typing import AsyncGenerator, NamedTuple

from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class MessageType(StrEnum):
    hello = auto()
    open = auto()
    accept = auto()


class Message(BaseModel):
    type: MessageType
    id: str | None = None
    port: str | None = None


class Stream(NamedTuple):
    reader: StreamReader
    writer: StreamWriter


async def _pipe(*, reader: StreamReader, writer: StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(1000)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as e:  # noqa: BLE001
        logger.debug(e)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception as e:  # noqa: BLE001
            logger.debug(e)


async def bridge(stream1: Stream, stream2: Stream) -> None:
    await asyncio.wait(
        [
            asyncio.create_task(_pipe(reader=stream1.reader, writer=stream2.writer)),
            asyncio.create_task(_pipe(reader=stream2.reader, writer=stream1.writer)),
        ],
        timeout=0,
        return_when=asyncio.FIRST_COMPLETED,
    )


async def read(reader: StreamReader) -> AsyncGenerator[Message, None]:
    while True:
        length_data = await reader.read(10)
        logger.debug(length_data)
        if not length_data:
            break
        message_length = int(length_data.decode().strip())
        message = (await reader.read(message_length)).decode()
        logger.debug(message)

        yield Message(**json.loads(message))


async def write(writer: StreamWriter, *, message: Message) -> None:
    message_data = message.model_dump_json()
    message_body = message_data.encode()
    message_header = f"{len(message_body):>10}".encode()

    writer.write(message_header + message_body)
    await writer.drain()
    logger.debug("Send message %s", message_data)
