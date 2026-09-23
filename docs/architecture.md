# Architecture Overview

***ts-obom*** is a small command line utility in Python. It scans a directory for infrastructure-as-code, lets a resource graph builder turn the templates into a graph of resources and their references, takes the inventory of declared resources from that graph, enriches it with the IAM grants the same graph carries, and writes the result as a CycloneDX Operations BOM.

## System Components

* **CLI** (`ts_obom.cli`): the click based command set, config and profile handling. Modelled on ts-scan's CLI so that both tools behave alike.
* **Extraction** (`ts_obom.obom`): the front-ends. Both take the inventory first -- every resource block in the graph becomes an `ObomResource` -- and then walk the same graph for IAM grants. `extract_cloudformation()` walks `AWS::IAM::Role` and `AWS::Serverless::Function` vertices, expands SAM policy templates from a built-in table and emits edges. `extract_terraform()` walks inline policy resources and policy attachments and resolves the role, user or group reference back to the compute resource that assumes it, where the graph allows it.
* **Vendored graph builder** (`ts_obom._vendor.checkov`): a trimmed subset of Checkov's CloudFormation and Terraform graph managers, about 25 real source files plus small stub modules for subsystems that are imported but never used on this path. It parses templates and `.tf` files, resolves `!Ref`, `!GetAtt`, Terraform variables and local modules, and produces the vertex and edge lists the extraction works on. See `NOTICE.md` in that directory for provenance and the exact changes.
* **Result model** (`ts_obom.ObomScan`): one document per scanned directory, with a header mirroring ts-scan's scan header and the `resources` / `edges` / `unresolved` lists.
* **CycloneDX output** (`ts_obom.cyclonedx`): turns a result into the document the TrustSource OBOM API accepts. The BOM skeleton comes from Checkov's own exporter (`checkov.common.output.cyclonedx`, vendored); ts-obom adds what Checkov cannot know -- the `trustsource:bomType = obom` marker, the module as `metadata.component`, component types beyond Checkov's blanket `application`, and the access grants as properties and `dependencies` edges. See ADR-006.
* **API client** (`ts_obom.api`): the TrustSource REST client, modelled on ts-scan's, with the API version in the base URL and the key in the `x-api-key` header. See ADR-007.

```
sources ──► graph builder (vendored checkov) ──► vertices/edges ──► extraction ──► ObomScan ──► ts | cyclonedx | dot
                                                                                                     │
                                                                                   ts-obom upload ───┘──► POST /core/imports/scan/obom
```

## Supported front-ends

| Front-end | Covered | Not covered yet |
|-----------|---------|-----------------|
| CloudFormation / SAM | Role inline policies, SAM function `Policies` (inline statements and the known policy templates) | `AWS::IAM::Policy` / `ManagedPolicy` resources, users and groups, resource based policies (bucket policies, queue policies) |
| Terraform / OpenTofu | `aws_iam_role_policy`, `aws_iam_user_policy`, `aws_iam_group_policy`, the three `*_policy_attachment` resources, role resolution to the compute resource through a `role` attribute (Lambda, EC2 instance profiles); `.tf`, `.tf.json`, `.tofu` and `.tofu.json` files with OpenTofu's precedence rule | `aws_iam_policy` documents referenced by attachment, `data.aws_iam_policy_document`, role resolution through `task_role_arn` / `execution_role_arn` (ECS) and `job_role_arn` (Batch), non-AWS providers |

Everything in the right column ends up in `unresolved` when it is referenced, and is the natural backlog.

OpenTofu is not a separate front-end. It is a fork of Terraform 1.5 with the same HCL language, provider blocks and resource types, and the scanner never executes either binary, so the `terraform` front-end covers both. The only OpenTofu-specific behaviour that matters for a file based scan is the `.tofu` extension introduced in OpenTofu 1.8, including its rule that `name.tofu` shadows `name.tf`; both are implemented in the vendored parser (see ADR-005). OpenTofu-only blocks such as state `encryption` are parsed as ordinary HCL and ignored.

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

### ADR-005 - Support OpenTofu through the Terraform front-end, with a minimal vendored-parser edit (2026-09-06, 0.1.0)

**Context.** OpenTofu projects are Terraform projects to a file based scanner, except that OpenTofu 1.8 introduced `.tofu` / `.tofu.json` files that shadow `.tf` files of the same name. Checkov's parser only collects `.tf`, `.tf.json` and `.hcl`, so `.tofu` files were silently skipped.

**Decision.** Keep one `terraform` front-end for both tools. Extend the vendored parser's file selection by the two OpenTofu extensions and implement the shadowing rule there; generalise the nested-module path helper that assumed a `.tf` suffix. Every edited line is marked with a `ts-obom:` comment and listed in `NOTICE.md`.

**Consequences.** OpenTofu code bases scan without any flag or conversion. The vendored copy now carries deliberate, documented edits in three files beyond the trimming, which must be re-applied when re-syncing with upstream Checkov.

### ADR-006 - The result is a CycloneDX Operations BOM, built by Checkov's own exporter (2026-09-22, 0.2.0)

**Context.** Up to 0.1.0 the scanner wrote a proprietary `{edges, unresolved}` document and its documentation described the OBOM as an *Ownership* Bill of Materials, explicitly distinct from CycloneDX's *Operations* BOM. That was a scope error. TrustSource's OBOM is an Operations BOM everywhere it exists on the platform -- the ingest Lambda, the REST API, the OpenAPI specification and the UI -- and it accepts only a CycloneDX document carrying `metadata.properties[] = {name: "trustsource:bomType", value: "obom"}`. A 0.1.0 result would have been rejected with a 400. Checkov, whose graph builder was already vendored, ships a CycloneDX exporter of its own (`checkov -o cyclonedx_json`), which emits one component per declared IaC resource -- exactly the inventory an Operations BOM is made of.

**Decision.** Produce a CycloneDX 1.6 document and build it with Checkov's exporter rather than a re-implementation, vendored from the same fork as the graph builder. ts-obom supplies what the exporter cannot know: the TrustSource marker, `metadata.component`, its own entry in `metadata.tools`, component types per resource type, and the access grants as namespaced `trustsource:obom:*` properties plus `dependencies` edges. The exporter is driven from a small stand-in for Checkov's `Report` so that its reporting subsystem stays out of the package.

**Consequences.** Component identity (the purl and the SHA-1 of the declaring file) is byte-for-byte what `checkov -o cyclonedx_json` produces for the same sources, so the two are comparable and a future upstream improvement is inherited rather than re-derived. The price is three new dependencies (`cyclonedx-python-lib`, `packageurl-python`, `termcolor`) and five modules restored from stubs in the vendored subset, all documented in `NOTICE.md`; the dependency conflict that originally motivated the vendoring was with ts-scan's pins and no longer applies (ADR-001). CycloneDX has no native model for an access grant, so the grants are carried in `properties` -- machine-readable, but a consumer has to know the namespace. The access graph itself is not lost: the native `ts` format keeps it in full, and `-f dot` still renders it.

### ADR-007 - Transfer follows ts-scan's client, with the API version in the base URL (2026-09-22, 0.2.0)

**Context.** The platform endpoint (`POST /core/imports/scan/obom`) resolves the scope -- which project, which module -- from query parameters, not from anything inside the document, and answers a rejected document with a 400 carrying its own messages. ts-scan already has a client for this API that CI pipelines know.

**Decision.** Copy ts-scan's client and command shape (`--base-url`, `--api-key`, `--project-name`, a file argument, profile and environment defaults) into `ts_obom.api` and `ts-obom upload`, with two deviations: the API version lives in the base URL (`https://api.trustsource.io/v2`) and the method paths are version-free, and errors carry the status code and the platform's own `messages`. ts-obom has exactly one transfer path -- the platform stores OBOMs as CycloneDX and nothing else -- so the command is named `upload` even though it posts to an import endpoint; a file in the native `ts` format is rejected locally, naming `-f cyclonedx`.

**Project scope is the default; module scope is the exception.** A module is a thing that produces a deployment artefact, which is why an SBOM and a SARIF report always have one. Infrastructure does not divide that way: a queue or a table belongs to no artefact, a function may belong to one, and a scan of the project root sees all of it at once (the front-ends recurse). So `ts-obom upload` without a module option is the normal case, and the documentation says so. `--module-name` is for the case where the scanned sources genuinely describe one module's own infrastructure -- not something to reach for by default in order to mirror the SBOM's module.

**Consequences.** An API version bump is one value in one place instead of an edit per call site, and a CI job configures it with `--base-url` alone. Pipelines that know ts-scan need no new vocabulary. The single-path naming avoids ts-scan's upload-versus-import trap by making the wrong file impossible to send rather than by documenting the distinction. Defaulting to project scope leaves the open question of what a project-scope OBOM means when it is uploaded twice -- `Obom.findLatest` returns the newest per scope, so a second upload shadows the first -- which is a platform question, tracked outside this repository.

### ADR-008 - Policy checks stay an optional extra; the scanner stays a scanner (2026-09-22, proposed)

**Context.** Checkov's check registry is the engine behind the `CKV_*` findings that map to the CIS AWS Foundations Benchmark, and its CycloneDX exporter -- the one ts-obom now builds on -- already turns findings into `vulnerabilities` entries on exactly the components ts-obom emits. The stand-in report ts-obom hands that exporter has the `failed_checks` / `passed_checks` fields already; they are simply empty. So shipping benchmark findings inside the OBOM is a small addition to the exporter path. What it is not small in is dependencies: the check registry is stubbed in the vendored subset, and vendoring it for real is close to vendoring all of Checkov.

**Decision.** If checks are added, they are an **optional extra** (`pip install ts-obom[checks]`) that depends on the real `checkov` package, never a default dependency and never a second vendored subtree. The base install stays what it is: a scanner that reads IaC and writes an OBOM. Evaluating that OBOM -- policies, benchmarks, risk -- is the platform's job, and ts-obom does not duplicate it. The extra exists so the tool still has standalone value for someone not using TrustSource, not because the pipeline needs it.

**And when they are added, they travel inside the OBOM, not as SARIF.** SARIF is the channel that already processes findings -- `POST /core/imports/tests/sarif` reconciles them into `riskProperties`, groups them by CWE and feeds the vulnerability alert evaluation -- but that processing is **module-anchored all the way down**: the route resolves a module with `create: true`, the tests are created against a `moduleId`, the CWE reconcile runs per module, and the risk identity (`riskProperties.autoKey`) is derived from a module id. Pushing infrastructure findings through it would mean inventing a module for something that produces no deployment artefact, which is precisely the mismatch that makes an OBOM a project-level document in the first place (ADR-007). A finding about a bucket policy would end up hanging off an artefact it has nothing to do with.

Carried in the OBOM, they stay where their subject is: at the project. From a project-level OBOM view they can be shown next to the resource they concern, tipped into risk management from there, and picked up by threat modelling -- and `riskProperties` already carries a `projectId`, so a project-anchored risk is not a new concept, only a new way in. The price is that the application side has to be built: nothing in ts-app reads `vulnerabilities` out of a stored OBOM today (checked 2026-09-22 -- the ingest Lambda stores the document verbatim, the UI renders `components[]` and the raw JSON), and a project-derived identity would be needed where the SARIF path uses a module-derived `autoKey`. That work is accepted deliberately rather than avoided by using a channel that would file the findings in the wrong place.

**Consequences.** The dependency footprint of a normal install does not move, and the offline guarantee (ADR-002) holds for everyone who does not opt in. ts-obom stays a producer of evidence and does not evaluate anything itself. Until the application side exists, findings shipped in an OBOM are inert -- visible in the raw document, acted on by nothing -- so the extra is worth building only together with, or after, that work; the ordering is a product decision, not a technical constraint. What deliberately stays open for now is the lifecycle: whether a finding is closed by a later version of the OBOM or simply disappears with it. Not scheduled; the backlog entry below records what would have to be built.

## Further development

Backlog, in rough order:

1. **Principal resolution for ECS and Batch (Terraform).** The role-to-principal resolution only follows the attributes `role`, `user` and `group`. `aws_ecs_task_definition` references its role through `task_role_arn` / `execution_role_arn`, `aws_batch_job_definition` through `job_role_arn`, so their grants are currently attributed to the IAM role instead of the task or job definition (visible in the `opentofu` test fixture). Extend `TF_PRINCIPAL_ATTRS` handling to these attributes and add both resource types to the fixtures.
2. **CIS benchmarks as an optional extra** (ADR-008, not scheduled). A `ts-obom[checks]` install would depend on the real `checkov` package, run a benchmark subset over the sources already scanned, and hand the findings to the exporter as `failed_checks` so they land as `vulnerabilities` on the components the OBOM already carries. Everything on the ts-obom side is in place for that -- `_InventoryReport` has the fields, checkov's exporter does the rest. The work that decides whether it is worth doing is on the platform: reading those findings out of a project-scope OBOM, showing them in the project view, and giving them a way into risk management with a project-derived identity.
3. `AWS::IAM::Policy` / `AWS::IAM::ManagedPolicy` resources and Terraform `aws_iam_policy` documents referenced by attachments.
4. Resource based policies (bucket, queue and topic policies).
5. A Kubernetes RBAC front-end.
