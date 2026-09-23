![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# TrustSource OBOM Scanner

The **ts-obom** scanner extracts an **Operations Bill of Materials (OBOM)** from infrastructure-as-code: the resources a module is deployed as -- functions, tables, buckets, queues, task definitions -- together with the IAM grants that say which of them may do what to which other. It reads CloudFormation, AWS SAM, Terraform and OpenTofu sources and writes a CycloneDX document that the TrustSource platform stores. It is the infrastructure counterpart to [ts-scan](https://github.com/trustsource/ts-scan), which produces the Software Bill of Materials (SBOM) of the code.

Where an SBOM answers *what is in the software*, an OBOM answers *what the software is operated as, and what it is allowed to touch once it runs*. That is the evidence trust-boundary and threat-modelling work needs and which SBOM signals alone cannot provide.

## Description

**ts-obom** scans a directory for IaC sources and emits, per scanned directory, a document with

* `resources` - every resource declared in the sources, with its type and the file it comes from. In the CycloneDX output these are the components
* `edges` - access grants `{principal, resource, actions[], effect, grantedVia}`, for example the role of a Lambda function that may `s3:GetObject` on a bucket ARN, with the policy or SAM policy template that granted it. In the CycloneDX output these are component properties and `dependencies` edges
* `unresolved` - grants the scanner saw but could not expand, for example managed policy ARNs that would need AWS API access to resolve

Supported IaC front-ends:

| Front-end | Sources | What is extracted |
|-----------|---------|-------------------|
| `cloudformation` | CloudFormation and AWS SAM templates (`.yaml`, `.yml`, `.json`) | `AWS::IAM::Role` inline policies, `AWS::Serverless::Function` policies including the common SAM policy templates (`DynamoDBCrudPolicy`, `S3ReadPolicy`, ...) |
| `terraform` | Terraform and OpenTofu (`.tf`, `.tf.json`, `.tofu`, `.tofu.json`; a `.tofu` file shadows a `.tf` file of the same name, as in OpenTofu) | `aws_iam_role_policy` / `aws_iam_user_policy` / `aws_iam_group_policy` inline documents, `*_policy_attachment` resources, resolved to the compute resource assuming the role where possible |

The graph is built with a trimmed, vendored subset of [Checkov](https://github.com/bridgecrewio/checkov)'s resource graph builder; see [`src/ts_obom/_vendor/NOTICE.md`](src/ts_obom/_vendor/NOTICE.md) for provenance and changes. No Checkov installation and no cloud credentials are required; the scan is fully offline.

## Installation

### Installation from the PyPI repository

```shell
pip install ts-obom
```

### Installation from a local folder

```shell
git clone https://github.com/trustsource/ts-obom.git
cd ts-obom
pip install .
```

### Installation as a Docker image

```shell
docker pull trustsource/ts-obom
```

Scan a local checkout by mounting it into the container:

```shell
docker run --rm -v "$(pwd)":/workspace trustsource/ts-obom scan -o /workspace/obom.json /workspace/infrastructure
```

## Usage

The command set follows the conventions of **ts-scan**: verbs as sub-commands, `-o/--output` and `-f/--format` for results, `--<front-end>:<option>` for front-end specific switches, a profile-based config file and an optional `tsproject.toml` in the scanned directory.

```shell
ts-obom scan -o <path to the output file> [-f <output format>] <path to one or more directories>
```

The `-f <output format>` option controls the output format and can be:

* `ts` - the scanner's own JSON format (default), one document per scanned directory
* `cyclonedx` - a CycloneDX 1.6 Operations BOM, the format the TrustSource platform stores
* `dot` - a Graphviz digraph of the access graph, for example `ts-obom scan -f dot infra | dot -Tsvg -o obom.svg`

### Options

* `--cloudformation:ignore` - Skip CloudFormation and SAM templates
* `--terraform:ignore` - Skip Terraform and OpenTofu sources
* `--tag <TAG>` - Stores the SCM tag `<TAG>` in the result
* `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the result
* `--verbose` - Enables verbose mode

The full list of options can be printed using:

```shell
ts-obom scan --help
```

### Example

Scanning a directory with a SAM template

```shell
ts-obom scan -o obom.json ./backend
```

produces a document like

```json
[
  {
    "module": "backend",
    "moduleId": "obom:backend",
    "source": "/work/orderdesk/backend",
    "tool": { "name": "ts-obom", "version": "0.2.0", "frontends": ["cloudformation", "terraform"], "generatedAt": "2026-09-22T12:00:00+00:00" },
    "edges": [
      {
        "principal": "AWS::Serverless::Function.OrderApiFunction",
        "resource": "Ref:OrdersTable",
        "actions": ["dynamodb:GetItem", "dynamodb:DeleteItem", "dynamodb:PutItem", "dynamodb:Scan", "dynamodb:Query", "dynamodb:UpdateItem", "dynamodb:BatchWriteItem", "dynamodb:BatchGetItem", "dynamodb:DescribeTable", "dynamodb:ConditionCheckItem"],
        "effect": "Allow",
        "grantedVia": "SAM policy template 'DynamoDBCrudPolicy'"
      }
    ],
    "unresolved": []
  }
]
```

The exact `principal`, `resource` and `grantedVia` strings depend on the front-end; the [format documentation](https://trustsource.github.io/ts-obom/format) describes them.

## Upload to TrustSource

The platform stores OBOMs as CycloneDX, so a transfer is a scan in that format followed by an upload:

```shell
ts-obom scan -f cyclonedx -o obom.cdx.json ./backend
ts-obom upload --api-key "$TS_API_KEY" --project-name Orderdesk --module-name backend obom.cdx.json
```

Name the **same module** the dependency scan uses, so the OBOM lands on the module its SBOM is on. Without a module option the OBOM is stored for the project as a whole. The `obom` feature has to be enabled for the company; the key travels as the `x-api-key` header, and `--base-url` carries the API version (default `https://api.trustsource.io/v2`).

Uploading a file written with `-f ts` is refused locally -- the API would only reject it -- with a pointer to `-f cyclonedx`.

## User Settings

Like **ts-scan**, **ts-obom** reads defaults from a TOML config file with profiles. The default location is `~/.ts-obom/config`; it is created on first run:

```toml
[default]
format = "ts"

[ci]
format = "ts"
verbose = true
```

Select a profile with `ts-obom -p ci scan ...` and a different file with `ts-obom --config <path> scan ...`. Options can also be set through environment variables prefixed with `TS_OBOM_`, for example `TS_OBOM_SCAN_OUTPUT_PATH`. A `tsproject.toml` in a scanned directory provides per-project defaults.

## Relationship to ts-scan

**ts-scan** and **ts-obom** are deliberately separate tools. Software composition (SBOM) and operational deployment (OBOM) are different questions with different consumers, and mixing them into one command set would blur what each result means. Both share the same conventions, packaging and release process, and the OBOM document header (`module`, `moduleId`, `source`, `tag`, `branch`) mirrors ts-scan's scan header so that results can be correlated per module.

## License

**ts-obom** is licensed under the Apache License 2.0. The vendored Checkov subset under `src/ts_obom/_vendor/checkov` is licensed under the Apache License 2.0 by its respective copyright holders; see the `LICENSE` and `NOTICE.md` files in that directory.
