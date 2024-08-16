# Pysubway
A HTTP tunnel service written in Python

## Usage

## Using Poethepoet
If you have poethepoet installed, you can use the following commands:

### Start Pysubway Server
```shell
poe server
```

### Start Pysubway Client
```shell
poe client --host <host> <local_port>
```


## Using Docker
If you prefer using Docker, pull the latest pysubway image:
```shell
docker pull ghcr.io/xianyuntang/pysubway
```

### Start Pysubway Server
```shell
docker run ghcr.io/xianyuntang/pysubway:latest poe server
```
Note: Ensure you bind the necessary ports (-p <host_port>:<container_port>) to expose the server properly.

### Start Pysubway Client
on Macos
```shell
docker run ghcr.io/xianyuntang/pysubway poe client --host <host> <local_port>
```
on Linux
```shell
docker run --network host ghcr.io/xianyuntang/pysubway poe client --host <host> <local_port>
```


