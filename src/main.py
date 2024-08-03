import asyncio
from argparse import ArgumentParser, Namespace

from src.client import Client
from src.server import Server


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description="subway")

    subparsers = parser.add_subparsers(dest="command")

    client_parser = subparsers.add_parser("client", help="Client command")
    client_parser.add_argument("local_port", type=str, help="local server host")
    client_parser.add_argument("--host", type=str, help="control server host")
    client_parser.add_argument(
        "--port", type=str, default="5678", help="control server port"
    )

    server_parser = subparsers.add_parser("server", help="Server command")
    server_parser.add_argument(
        "-p", "--port", type=str, default="5678", help="control port"
    )

    return parser


async def handle_client(args: Namespace) -> None:
    client = Client(
        control_host=args.host, control_port=args.port, local_port=args.local_port
    )
    await client.listen()


async def handle_server(args: Namespace) -> None:
    server = Server(control_port=args.port)
    await server.listen()


async def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    if args.command == "client":
        await handle_client(args)
    elif args.command == "server":
        await handle_server(args)


if __name__ == "__main__":
    asyncio.run(main())
