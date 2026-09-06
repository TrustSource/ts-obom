# Installation

Installation is fairly simple. We provide ts-obom as a PIP package. You will require a recent Python version (v3.10, v3.11 and v3.12 are tested) and pip (v22+).

### Installation from the PyPI repository

```
pip install ts-obom
```

Everything the scanner needs is a regular dependency of the package. There is no optional extra and no separate Checkov installation.

### Installation from a local folder

Alternatively you may clone the repository and install it directly into your environment:

```
git clone https://github.com/trustsource/ts-obom.git
cd ts-obom
pip install .
```

For development install the `dev` extra as well, which adds pytest and pyright:

```
pip install '.[dev]'
```

## Docker image

Every release is published as `trustsource/ts-obom` on Docker Hub, tagged with the release version and `latest`:

```
docker pull trustsource/ts-obom
```

See [Operating inside a container](container.md) for how to mount your sources.

## Verify the installation

```
ts-obom --version
ts-obom scan --help
```
