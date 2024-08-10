from __future__ import annotations

import asyncio
import ssl
import time
from pathlib import Path
from typing import NamedTuple

import aiohttp
import uvloop
from aiohttp.web import Application, AppRunner, Request, Response, TCPSite

from src.const import DEFAULT_DOMAIN, EXPIRE_TIME, LOCAL_BIND
from src.logger import logger

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Upstream(NamedTuple):
    url: str
    expire_in: float


class Proxy:
    def __init__(self, *, domain: str, use_ssl: bool) -> None:
        self.upstreams: dict[str, Upstream] = {}
        self.domain = domain
        self.use_ssl = use_ssl
        self.protocol = "https" if use_ssl else "http"
        self.port = 443 if use_ssl else 80
        self.expire_after = 3600

        app = Application()
        app.router.add_route("*", "/{tail:.*}", self.proxy)

        self.app = app

    def _clean_up(self) -> None:
        now = time.time()

        to_be_cleaned = []
        for key, upstream in self.upstreams.items():
            if upstream.expire_in < now:
                to_be_cleaned.append(key)
        for key in to_be_cleaned:
            self.upstreams.pop(key)
        logger.info(f"Cleaning up... delete {len(to_be_cleaned)} endpoint")

    def _build_endpoint(self, *, subdomain: str) -> str:
        return f"{self.protocol}://{subdomain}.{self.domain}"

    def _get_upstream(self, *, host: str) -> Upstream | None:
        if host.endswith(f"{self.domain}"):
            subdomain = host.replace(f".{self.domain}", "")
            upstream = self._build_endpoint(subdomain=subdomain)
            return self.upstreams.get(upstream, None)
        return None

    def register_upstream(self, *, subdomain: str, port: str) -> str:
        endpoint = self._build_endpoint(subdomain=subdomain)
        self.upstreams[endpoint] = Upstream(
            url=f"http://{LOCAL_BIND}:{port}", expire_in=time.time() + EXPIRE_TIME
        )
        return endpoint

    async def proxy(self, request: Request) -> Response:
        async with aiohttp.ClientSession() as session:
            upstream = self._get_upstream(host=request.host)
            if upstream is None:
                return Response(
                    body="404 Not Found",
                    status=404,
                    content_type="text/html",
                )

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
            self._clean_up()
            await asyncio.sleep(60)


if __name__ == "__main__":
    proxy = Proxy(domain=DEFAULT_DOMAIN, use_ssl=False)
    proxy.register_upstream(subdomain="sdfsd", port="444")
    asyncio.run(proxy.listen())
