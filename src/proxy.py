from __future__ import annotations

import asyncio
import re
import ssl
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, NamedTuple, cast

import aiohttp
from aiohttp.web import Application, AppRunner, Request, Response, TCPSite
from nanoid import generate

from src.const import CLEAN_UP_INTERVAL, EXPIRE_TIME, LOCAL_BIND
from src.logger import logger


class Upstream(NamedTuple):
    host: str
    port: int
    expire_in: float

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class Proxy:
    def __init__(
        self,
        *,
        domain: str,
        use_ssl: bool,
        behind_proxy: bool,
        end_connection: Callable[[int], Coroutine[Any, Any, None]],
    ) -> None:
        self.domain = domain
        self.use_ssl = use_ssl
        self.behind_proxy = behind_proxy
        self.protocol = "https" if use_ssl else "http"
        self.port = 443 if use_ssl else 80
        self.expire_after = 3600
        self.end_connection = end_connection

        self.upstreams: dict[str, Upstream] = {}

        app = Application()
        app.router.add_route("*", "/{tail:.*}", self.proxy)

        self.app = app

    async def _clean_up(self) -> None:
        now = time.time()

        to_be_cleaned = []
        for key, upstream in self.upstreams.items():
            if upstream.expire_in < now:
                to_be_cleaned.append(key)
        for key in to_be_cleaned:
            upstream = self.upstreams.pop(key)
            await self.end_connection(upstream.port)

        logger.debug(f"Cleaning up... delete {len(to_be_cleaned)} endpoint")

    def _build_endpoint(self, *, subdomain: str) -> str:
        return f"{self.protocol}://{subdomain}.{self.domain}"

    def _get_upstream(self, *, subdomain: str) -> Upstream | None:
        return self.upstreams.get(subdomain, None)

    def _get_host(self, *, request: Request) -> str | None:
        if self.behind_proxy:
            return request.headers.get("X-Forwarded-Host")
        return request.host

    def _extract_subdomain(self, *, host: str) -> str | None:
        match = re.search(r"([^.]+)\.[^.]+\.[^.]+(?:/.*)?$", host)
        if match:
            return match.group(1)
        return None

    def register_upstream(self, *, port: int, subdomain: str) -> str:
        endpoint = self._build_endpoint(subdomain=subdomain)
        self.upstreams[subdomain] = Upstream(
            host=LOCAL_BIND, port=port, expire_in=time.time() + EXPIRE_TIME
        )
        return endpoint

    async def _gen_404_response(self) -> Response:
        return Response(
            body="404 Not Found",
            status=404,
            content_type="text/html",
        )

    def gen_subdomain(self, subdomain: str | None) -> str:
        if subdomain is None or subdomain in self.upstreams:
            return cast(
                str, generate(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", size=12)
            )

        return subdomain

    async def proxy(self, request: Request) -> Response:
        async with aiohttp.ClientSession() as session:
            host = self._get_host(request=request)
            if host is None:
                return await self._gen_404_response()

            subdomain = self._extract_subdomain(host=host)
            if subdomain is None:
                return await self._gen_404_response()

            logger.info(f"Received request from host {host}")
            upstream = self._get_upstream(subdomain=subdomain)
            if upstream is None:
                return await self._gen_404_response()

            async with session.request(
                url=f"{upstream.url}{request.path}",
                method=request.method,
                headers=request.headers,
                data=await request.read(),
            ) as resp:
                body = await resp.read()
                return Response(
                    body=body,
                    status=resp.status,
                    content_type=resp.content_type,
                    charset=resp.charset,
                )

    async def listen(self) -> None:
        ssl_context = None
        if self.use_ssl:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                certfile=Path("~/.pysubway/ssl/domain.cert.pem").expanduser(),
                keyfile=Path("~/.pysubway/ssl/private.key.pem").expanduser(),
            )

        runner = AppRunner(self.app)
        await runner.setup()
        site = TCPSite(runner, LOCAL_BIND, int(self.port), ssl_context=ssl_context)
        await site.start()
        logger.info(
            f"Proxy server listen on {self.protocol}://{LOCAL_BIND}:{self.port}"
        )
        logger.info(
            f"Proxy server will be serving your services on "
            f"{self.protocol}://<subdomain>.{self.domain}"
        )

        while True:
            await self._clean_up()
            await asyncio.sleep(CLEAN_UP_INTERVAL)
