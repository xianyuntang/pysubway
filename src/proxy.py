from __future__ import annotations

import asyncio
import ssl
from pathlib import Path

import aiohttp
import uvloop
from aiohttp.web import Application, AppRunner, Request, Response, TCPSite

from src.logger import logger
from src.shared import DEFAULT_DOMAIN, LOCAL_BIND

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Proxy:
    def __init__(self, *, domain: str, port: str, use_ssl: bool) -> None:
        self.hosts: dict[str, str] = {}
        self.domain = domain
        self.port = port
        self.use_ssl = use_ssl

        app = Application()
        app.router.add_route("*", "/{tail:.*}", self.proxy)

        self.app = app

    def _build_upstream(self, *, subdomain: str) -> str:
        prefix = "https" if self.use_ssl else "http"
        return f"{prefix}://{subdomain}.{self.domain}:{self.port}"

    def _get_upstream(self, *, host: str) -> str | None:
        if host.endswith(f"{self.domain}:{self.port}"):
            subdomain = host.replace(f".{self.domain}:{self.port}", "")
            upstream = self._build_upstream(subdomain=subdomain)
            return self.hosts.get(upstream, None)
        return None

    def register_upstream(self, *, subdomain: str, port: str) -> str:
        upstream_url = self._build_upstream(subdomain=subdomain)
        self.hosts[upstream_url] = f"http://{LOCAL_BIND}:{port}"
        return upstream_url

    async def proxy(self, request: Request) -> Response:
        async with aiohttp.ClientSession() as session:
            upstream = self._get_upstream(host=request.host)
            if upstream is None:
                return Response(body="404 Not Found", status=404)

            async with session.request(
                method=request.method,
                url=upstream,
                headers=request.headers,
                data=await request.read(),
            ) as resp:
                headers = dict(resp.headers.items())
                body = await resp.read()
                return Response(body=body, status=resp.status, headers=headers)

    async def listen(self) -> None:
        ssl_context = None
        if self.use_ssl:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                certfile=Path("~/.subway/ssl/domain.cert.pem").expanduser(),
                keyfile=Path("~/.subway/ssl/private.key.pem").expanduser(),
            )

        runner = AppRunner(self.app)
        await runner.setup()
        site = TCPSite(runner, LOCAL_BIND, int(self.port), ssl_context=ssl_context)
        await site.start()
        logger.info(f"Proxy server listen on {LOCAL_BIND}:{self.port}")
        logger.info(f"Proxy server will be serving your services on *.{self.domain}")

        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    proxy = Proxy(domain=DEFAULT_DOMAIN, use_ssl=False, port="5679")
    asyncio.run(proxy.listen())
