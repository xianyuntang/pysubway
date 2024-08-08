# Subway
A HTTP tunnel service written in Python

## Usage

### Start Subway Server
```shell
python -m src.main server
```

### Start Subway Client
```shell
python -m src.main client --host <host> <local_port>
```

## Using Poethepoet
If you have poethepoet installed, you can use the following commands:

### Start Subway Server
```shell
poe server
```

### Start Subway Client
```shell
poe client --host <host> <local_port>
```


## Using Docker
If you prefer using Docker, pull the latest Subway image:
```shell
docker pull ghcr.io/xianyuntang/subway:latest
```

### Start Subway Server
```shell
docker run ghcr.io/xianyuntang/subway:latest poe server
```
Note: Ensure you bind the necessary ports (-p <host_port>:<container_port>) to expose the server properly.

### Start Subway Client
```shell
docker run ghcr.io/xianyuntang/subway:latest poe client --host <host> <local_port>
```