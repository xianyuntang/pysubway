# pysubway
A HTTP tunnel service written in Python

## Usage

### Start pysubway Server
```shell
python -m src.main server
```

### Start pysubway Client
```shell
python -m src.main client --host <host> <local_port>
```

## Using Poethepoet
If you have poethepoet installed, you can use the following commands:

### Start pysubway Server
```shell
poe server
```

### Start pysubway Client
```shell
poe client --host <host> <local_port>
```


## Using Docker
If you prefer using Docker, pull the latest pysubway image:
```shell
docker pull ghcr.io/xianyuntang/pysubway:latest
```

### Start pysubway Server
```shell
docker run ghcr.io/xianyuntang/pysubway:latest poe server
```
Note: Ensure you bind the necessary ports (-p <host_port>:<container_port>) to expose the server properly.

### Start pysubway Client
```shell
docker run ghcr.io/xianyuntang/pysubway:latest poe client --host <host> <local_port>
```