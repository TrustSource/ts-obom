# Operating inside a container

Every release of ***ts-obom*** is published as the Docker image `trustsource/ts-obom`, tagged with the version and `latest`. The image contains only Python and the scanner; no cloud CLI, no Terraform.

## Scan a local checkout

Mount the sources into `/workspace`, the image's working directory, and pass paths relative to it:

```shell
docker run --rm -v "$(pwd)":/workspace trustsource/ts-obom scan -o /workspace/obom.json infrastructure
```

The result is written into the mounted directory. Without `-o` it is printed to standard output, which is convenient for piping:

```shell
docker run --rm -v "$(pwd)":/workspace trustsource/ts-obom scan -f dot infrastructure | dot -Tsvg -o obom.svg
```

## Configuration in a container

The config file is looked up at `~/.ts-obom/config` inside the container, which is empty on every run. Either mount a config file

```shell
docker run --rm -v "$(pwd)":/workspace -v "$HOME/.ts-obom:/root/.ts-obom" trustsource/ts-obom scan infrastructure
```

or use environment variables with the `TS_OBOM_` prefix:

```shell
docker run --rm -e TS_OBOM_SCAN_FORMAT=dot -v "$(pwd)":/workspace trustsource/ts-obom scan infrastructure
```

## Build the image yourself

```shell
docker build -t ts-obom .
```

The image is built from the repository's `Dockerfile`; the CI workflow builds and pushes it whenever a version tag is pushed.
