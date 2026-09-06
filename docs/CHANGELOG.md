# ts-obom Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-06

### New Features
    * Initial release as a standalone tool, extracted from the `obom` branch of ts-scan
    * `ts-obom scan` extracts IAM access grants from CloudFormation / AWS SAM templates and Terraform sources into the TrustSource OBOM JSON format
    * `-f dot` renders the access graph as a Graphviz digraph
    * `--cloudformation:ignore` and `--terraform:ignore` switch individual IaC front-ends off, following ts-scan's option conventions
    * Profile-based config file (`~/.ts-obom/config`), `tsproject.toml` project defaults and `TS_OBOM_` environment variables
    * Docker image `trustsource/ts-obom` and PyPI package `ts-obom`, released from version tags

### Improvements
    * The vendored Checkov graph-builder subset ships with its Apache-2.0 LICENSE and a NOTICE documenting provenance and changes
