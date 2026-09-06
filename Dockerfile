FROM python:3.12-slim
LABEL maintainer="TrustSource Team <support@trustsource.io>"

RUN mkdir -p /tmp/ts-obom
WORKDIR /tmp/ts-obom

COPY ./src ./src
COPY ./pyproject.toml ./LICENSE ./README.md ./

RUN pip install --no-cache-dir . \
    && rm -rf /tmp/ts-obom/src

WORKDIR /workspace

ENTRYPOINT ["ts-obom"]
CMD []
