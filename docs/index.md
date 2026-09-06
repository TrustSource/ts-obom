![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# Overview

***ts-obom*** extracts an **Ownership Bill of Materials (OBOM)** from infrastructure-as-code. The OBOM is an access graph: which identity (a Lambda function's role, a task definition's role, an IAM user or group) may perform which actions on which resource, and through which policy that grant was made.

It is the infrastructure counterpart to [ts-scan](https://trustsource.github.io/ts-scan), which builds the Software Bill of Materials. An SBOM tells you what is inside the software; the OBOM tells you what the software is allowed to touch once it runs. Together they give threat modelling and trust-boundary analysis the evidence that neither can provide alone.

***ts-obom*** works entirely offline on CloudFormation, AWS SAM, Terraform and OpenTofu sources. It needs no cloud credentials, no Terraform init and no Checkov installation.

To get started:

- [Architecture and supported front-ends](/ts-obom/architecture)
- [Installation](/ts-obom/setup)
- [Usage](/ts-obom/usage) and the [result format](/ts-obom/format)
- [Operating inside a container](/ts-obom/container)

## Getting Support

***ts-obom*** is open source and supported through this repository. As a TrustSource subscriber, you may contact [TrustSource support](mailto:support@trustsource.io) for help. As a community user, please [file a ticket with the repo](https://github.com/trustsource/ts-obom/issues).

You may also find additional information and learning materials in our open [TrustSource Knowledgebase](https://support.trustsource.io).

## Reporting Vulnerabilities

TrustSource supports a coordinated vulnerability disclosure procedure for its platform. ***ts-obom*** follows that schema and vulnerabilities identified should follow this procedure. Please find all details in our [Security](security.md) Policy.
