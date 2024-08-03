from __future__ import annotations

import asyncio
import json
import logging
from asyncio import CancelledError, StreamReader, StreamWriter
from enum import StrEnum, auto
from typing import AsyncGenerator, NamedTuple

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class MessageType(StrEnum):
    hello = auto()
    open = auto()
    accept = auto()
    connection = auto()


class Stream(NamedTuple):
    reader: StreamReader
    writer: StreamWriter


TIMEOUT = 50 * 0.001


async def _pipe(*, reader: StreamReader, writer: StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(100)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except CancelledError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def proxy(stream1: Stream, stream2: Stream) -> None:
    await asyncio.wait(
        [
            asyncio.create_task(_pipe(reader=stream1.reader, writer=stream2.writer)),
            asyncio.create_task(_pipe(reader=stream2.reader, writer=stream1.writer)),
        ],
        timeout=TIMEOUT,
        return_when=asyncio.FIRST_COMPLETED,
    )

    await asyncio.sleep(TIMEOUT)


async def read(reader: StreamReader) -> AsyncGenerator[dict[str, str], None]:
    while True:
        length_data = await reader.read(10)
        logger.info(length_data)
        if not length_data:
            break
        message_length = int(length_data.decode().strip())
        message = (await reader.read(message_length)).decode()
        logger.info(message)

        yield json.loads(message)


async def write(
    writer: StreamWriter, *, message_type: MessageType, **kwargs: str
) -> None:
    message_data = json.dumps({"message_type": message_type, **kwargs})
    message_body = message_data.encode()
    message_header = f"{len(message_body):>10}".encode()

    writer.write(message_header + message_body)
    await writer.drain()
    logger.debug("Send message %s", message_data)
