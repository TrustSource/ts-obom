# Architecture Overview

***ts-obom*** is a small command line utility in Python. It scans a directory for infrastructure-as-code, lets a resource graph builder turn the templates into a graph of resources and their references, and walks that graph for IAM grants.

## System Components

* **CLI** (`ts_obom.cli`): the click based command set, config and profile handling. Modelled on ts-scan's CLI so that both tools behave alike.
* **Extraction** (`ts_obom.obom`): the front-ends. `extract_cloudformation()` walks `AWS::IAM::Role` and `AWS::Serverless::Function` vertices, expands SAM policy templates from a built-in table and emits edges. `extract_terraform()` walks inline policy resources and policy attachments and resolves the role, user or group reference back to the compute resource that assumes it, where the graph allows it.
* **Vendored graph builder** (`ts_obom._vendor.checkov`): a trimmed subset of Checkov's CloudFormation and Terraform graph managers, about 25 real source files plus small stub modules for subsystems that are imported but never used on this path. It parses templates and `.tf` files, resolves `!Ref`, `!GetAtt`, Terraform variables and local modules, and produces the vertex and edge lists the extraction works on. See `NOTICE.md` in that directory for provenance and the exact changes.
* **Result model** (`ts_obom.ObomScan`): one document per scanned directory, with a header mirroring ts-scan's scan header and the `edges` / `unresolved` lists.

```
sources ──► graph builder (vendored checkov) ──► vertices/edges ──► extraction ──► ObomScan ──► ts | dot
```

## Supported front-ends

| Front-end | Covered | Not covered yet |
|-----------|---------|-----------------|
| CloudFormation / SAM | Role inline policies, SAM function `Policies` (inline statements and the known policy templates) | `AWS::IAM::Policy` / `ManagedPolicy` resources, users and groups, resource based policies (bucket policies, queue policies) |
| Terraform | `aws_iam_role_policy`, `aws_iam_user_policy`, `aws_iam_group_policy`, the three `*_policy_attachment` resources, role resolution to Lambda, ECS, EC2 and Batch | `aws_iam_policy` documents referenced by attachment, `data.aws_iam_policy_document`, non-AWS providers |

Everything in the right column ends up in `unresolved` when it is referenced, and is the natural backlog.

## Architecture Decision Records

### ADR-001 - ts-obom is a separate tool, not a ts-scan option (2026-09-06, 0.1.0)

**Context.** The extraction was first developed on a branch of ts-scan as `ts-scan scan --include-obom`. The ts-scan maintainer rejected the integration: an access graph is not software composition analysis, and adding it to the SBOM command set would confuse customers about what ts-scan produces.

**Decision.** Move the code into its own repository and package, `ts-obom`, with its own command, release process and documentation. Follow ts-scan's CLI conventions, packaging and site structure so that the two tools feel like one family.

**Consequences.** Clear product boundaries and independent release cadence. The price is a second tool to install and a second pipeline step; both are mitigated by identical conventions and a shared Docker Hub and PyPI namespace.

### ADR-002 - Vendor a trimmed Checkov graph builder instead of depending on the checkov package (2026-08-27, 0.1.0)

**Context.** The full `checkov` distribution pins `importlib-metadata`, `cyclonedx-python-lib` and `packageurl-python` to versions that conflict with ts-scan, where the code originally lived, and drags in CVE scanning, reporting and platform integration code that the graph builder never uses.

**Decision.** Copy the roughly 25 files the graph builder actually needs, stub the imported-but-unused subsystems, keep Checkov's Apache-2.0 LICENSE and document every change in `NOTICE.md`.

**Consequences.** A light dependency footprint and a scan that runs offline. Upstream changes to Checkov's graph builder must be re-vendored deliberately rather than picked up by a version bump; the NOTICE describes the procedure. Now that the code lives outside ts-scan the original version conflict no longer applies, so a future ADR may revisit this and depend on `checkov` directly if its dependency set becomes acceptable.

### ADR-003 - Result header mirrors ts-scan's scan header (2026-09-06, 0.1.0)

**Context.** OBOM results will be correlated with SBOM results per module, on the TrustSource platform and in threat modelling.

**Decision.** Every result document starts with `module`, `moduleId`, `source`, `tag` and `branch` exactly as a ts-scan dependency scan does, with `moduleId` prefixed `obom:`. The graph follows under `edges` and `unresolved`.

**Consequences.** Results from both tools can be joined on module identity without an adapter. The OBOM keeps its own body; it is not squeezed into a dependency tree.

### ADR-004 - Environment variable prefix `TS_OBOM_` instead of ts-scan's `TS_` (2026-09-06, 0.1.0)

**Context.** click derives environment variable names from the command and option names. With ts-scan's prefix, `ts-obom scan --output` and `ts-scan scan --output` would both read `TS_SCAN_OUTPUT_PATH`.

**Decision.** Use `TS_OBOM_` as the prefix.

**Consequences.** Both tools can be configured in the same CI job without interference, at the cost of one small deviation from ts-scan's conventions, documented in the usage guide.

## Further development

Planned next steps, in rough order: upload of OBOM results to the TrustSource platform once the API endpoint exists; `AWS::IAM::Policy` and `aws_iam_policy` documents; resource based policies; a Kubernetes RBAC front-end.
