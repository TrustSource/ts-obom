![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# TrustSource OBOM Scanner

The **ts-obom** scanner extracts an **Ownership Bill of Materials (OBOM)** from infrastructure-as-code: a graph of *who may do what to which resource*, derived from the IAM roles, policies and policy attachments declared in CloudFormation, AWS SAM, Terraform and OpenTofu sources. It is the infrastructure counterpart to [ts-scan](https://github.com/trustsource/ts-scan), which produces the Software Bill of Materials (SBOM) of the code.

Where an SBOM answers *what is in the software*, an OBOM answers *which identities the software runs as and what they are allowed to touch*. That is the evidence trust-boundary and threat-modelling work needs and which SBOM signals alone cannot provide.

## Description

**ts-obom** scans a directory for IaC sources and emits, per scanned directory, a document with

* `edges` - access grants `{principal, resource, actions[], effect, grantedVia}`, for example the role of a Lambda function that may `s3:GetObject` on a bucket ARN, with the policy or SAM policy template that granted it
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

* `ts` - the TrustSource OBOM JSON format (default), one document per scanned directory
* `dot` - a Graphviz digraph for visualisation, for example `ts-obom scan -f dot infra | dot -Tsvg -o obom.svg`

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
    "tool": { "name": "ts-obom", "version": "0.1.0", "frontends": ["cloudformation", "terraform"], "generatedAt": "2026-09-06T12:00:00+00:00" },
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

**ts-scan** and **ts-obom** are deliberately separate tools. Software composition (SBOM) and access rights (OBOM) are different questions with different consumers, and mixing them into one command set would blur what each result means. Both share the same conventions, packaging and release process, and the OBOM document header (`module`, `moduleId`, `source`, `tag`, `branch`) mirrors ts-scan's scan header so that results can be correlated per module.

## License

**ts-obom** is licensed under the Apache License 2.0. The vendored Checkov subset under `src/ts_obom/_vendor/checkov` is licensed under the Apache License 2.0 by its respective copyright holders; see the `LICENSE` and `NOTICE.md` files in that directory.
