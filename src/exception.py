class LocalhostUnreachableError(Exception):
    def __init__(self) -> None:
        super().__init__("Localhost is unreachable")
