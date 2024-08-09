from __future__ import annotations

import asyncio
import ssl
from pathlib import Path

import aiohttp
from aiohttp.web import Application, AppRunner, Request, Response, TCPSite

from src.logger import logger
from src.shared import DEFAULT_DOMAIN, LOCAL_BIND


class Proxy:
    def __init__(self, *, domain: str, port: str, use_ssl: bool) -> None:
        self.hosts: dict[str, str] = {}
        self.domain = domain
        self.port = port
        self.use_ssl = use_ssl

        app = Application()
        app.router.add_route("*", "/{tail:.*}", self.proxy)

        self.app = app

    def register_upstream(self, *, domain_prefix: str, port: str) -> str:
        prefix = "https" if self.use_ssl else "http"
        self.hosts[domain_prefix] = f"{prefix}://{LOCAL_BIND}:{port}"
        return f"{prefix}://{domain_prefix}-{self.domain}"

    def _get_upstream_url(self, *, host: str) -> str | None:
        if host.endswith(self.domain):
            domain_prefix = host.replace(f"-{self.domain}", "")
            return self.hosts.get(domain_prefix, None)

        return None

    async def proxy(self, request: Request) -> Response:
        async with aiohttp.ClientSession() as session:
            upstream = self._get_upstream_url(host=request.host)
            if upstream is None:
                return Response(body="Page not found", status=404)

            async with session.request(
                method=request.method,
                url=upstream,
                headers=request.headers,
                data=await request.read(),
            ) as resp:
                headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() != "content-encoding"
                }
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
