from argparse import ArgumentParser, Namespace

import uvloop

from src.client import Client
from src.server import Server


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description="pysubway")

    subparsers = parser.add_subparsers(dest="command")

    client_parser = subparsers.add_parser("client")
    client_parser.add_argument("local_port", type=int)
    client_parser.add_argument("--host", type=str)
    client_parser.add_argument(
        "--port",
        type=int,
    )

    server_parser = subparsers.add_parser("server")
    server_parser.add_argument(
        "--control_port",
        type=int,
    )
    server_parser.add_argument(
        "--use_ssl",
        type=lambda v: v.lower() in ["true", "1", "yes"],
    )
    server_parser.add_argument(
        "--domain",
        type=str,
    )
    server_parser.add_argument(
        "--behind_proxy",
        type=lambda v: v.lower() in ["true", "1", "yes"],
    )

    return parser


async def handle_client(args: Namespace) -> None:
    client = Client(
        control_host=args.host, control_port=args.port, local_port=args.local_port
    )
    await client.listen()


async def handle_server(args: Namespace) -> None:
    server = Server(
        control_port=args.control_port,
        domain=args.domain,
        use_ssl=args.use_ssl,
        behind_proxy=args.behind_proxy,
    )
    await server.listen()


async def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    if args.command == "client":
        await handle_client(args)
    elif args.command == "server":
        await handle_server(args)


if __name__ == "__main__":
    uvloop.run(main())
