# Usage

***ts-obom*** follows the command conventions of ***ts-scan***: verbs as sub-commands, `-o/--output` and `-f/--format` for results, `--<front-end>:<option>` for front-end specific switches, a profile based config file and an optional `tsproject.toml` in the scanned directory. If you know ts-scan, ts-obom will feel familiar.

## Scan

The **scan** command searches one or more directories for infrastructure-as-code sources, builds the resource graph and extracts the IAM access grants.

```shell
ts-obom scan -o <path to the output file> [-f <output format>] <path to one or more directories>
```

Every directory produces one result document. Directories are scanned recursively by the IaC front-ends; a file argument is treated as its parent directory.

The `-f <output format>` option controls the output format and can be:

* `ts` - the scanner's own JSON format (default), one document per scanned directory, see [Result format](format.md)
* `cyclonedx` - a CycloneDX 1.6 Operations BOM. This is the format the TrustSource platform stores, and the one [`ts-obom upload`](#upload) sends. A CycloneDX document describes exactly one subject, so this format takes exactly one source directory:

```shell
ts-obom scan -f cyclonedx -o obom.cdx.json ./backend
```

* `dot` - a Graphviz digraph of the access graph, one cluster per scanned directory. Render it with Graphviz, for example:

```shell
ts-obom scan -f dot ./infrastructure | dot -Tsvg -o obom.svg
```

Without `-o` the result is printed to standard output.

### Options

Front-end specific options are prefixed with the front-end name, like package manager options in ts-scan:

* `--cloudformation:ignore` - Skip CloudFormation and AWS SAM templates
* `--terraform:ignore` - Skip Terraform and OpenTofu sources (OpenTofu is handled by the `terraform` front-end; the two share the HCL language)

General options:

* `--cloudformation:parameters <FILE>` - Applies a CloudFormation parameter file on top of the template defaults
* `--terraform:var-file <FILE>` - Applies a `.tfvars` file on top of the variable defaults, as `terraform -var-file` would
* `--deployment <NAME>` - Names the deployment this OBOM describes: an environment (`DEV`, `PRD`) or a customer setup (`kunde1`). See [Deployments](#deployments) below
* `--tag <TAG>` - Stores the SCM tag `<TAG>` in the result
* `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the result
* `--verbose` - Enables verbose mode

### Deployments

One project is usually deployed several times -- `DEV` and `PRD`, or one setup per customer. `--deployment` names which of them a document describes, so the platform can hold them side by side and a reader can ask what production has that development does not.

```shell
ts-obom scan -f cyclonedx --deployment PRD \
  --cloudformation:parameters params4PRD.json -o obom-prd.cdx.json .
```

**A name alone is not enough.** The scan resolves `Ref`, `!Sub` and Terraform variables against the **defaults declared in the sources**. In the common pattern -- one template, one parameter file per environment -- the entire difference between two deployments lives in those parameter files, and without them two scans of the same sources produce identical documents. Naming one `DEV` and the other `PRD` would then show "no difference" where in truth nothing was compared.

Every result therefore records where its parameter values came from, in `parameterSource`:

| Value | Meaning |
|-------|---------|
| `defaults` | No parameter values were supplied to any front-end. Two documents that both say this are **not** comparable, however they are named |
| `cloudformation=params4PRD.json` | CloudFormation values came from that file |
| `cloudformation=defaults,terraform=params4PRD.tfvars` | Half parameterised -- Terraform got values, CloudFormation did not |

Naming a deployment without supplying parameter values is allowed and warned about, at scan time and again at upload.

### Parameter files

`--cloudformation:parameters` reads the format TrustSource's own deploy scripts use, which is also what `aws cloudformation --parameters` takes:

```json
[
  { "ParameterKey": "BucketName", "ParameterValue": "orderdesk-prod-reports" }
]
```

A flat `{"BucketName": "orderdesk-prod-reports"}` mapping works as well, with or without a `Parameters` wrapper; which one it is is told from the file, not from a flag. The values replace the templates' declared `Default`s before the graph is built. A parameter the file does not name keeps its template default, exactly as it would on a real deployment.

A value supplied for a parameter **no scanned template declares** -- usually a typo or the wrong file -- is reported under `unresolved` with the reason `unused-parameter`, rather than silently ignored.

`--terraform:var-file` takes a `.tfvars` file and applies it the way `terraform -var-file` does, on top of the variable defaults and the files Terraform loads automatically.

The full list of options can be printed using:

```shell
ts-obom scan --help
```

## Upload

The **upload** command transfers a CycloneDX OBOM to the TrustSource platform.

```shell
ts-obom upload --api-key <API key> --project-name <project> [--module-name <module>] <path to the OBOM>
```

The document must be in the `cyclonedx` format; a file written with `-f ts` is refused before anything is sent. A full run is therefore two commands:

```shell
ts-obom scan -f cyclonedx -o obom.cdx.json .
ts-obom upload --api-key "$TS_API_KEY" --project-name Orderdesk obom.cdx.json
```

Scan the **project root**, not single subdirectories: the front-ends recurse, so one run covers every template and `.tf` file below it, and the result is one document for the whole project. That matches where an OBOM belongs -- see below.

### Options

* `--api-key <KEY>` - TrustSource API key. Sent as the `x-api-key` header, never in the body or the URL
* `--base-url <URL>` - API base URL **including the API version**, default `https://api.trustsource.io/v2`. The version lives here and nowhere else, so pointing at another version or another installation is one option
* `--project-name <NAME>` - the project the OBOM belongs to. The project must already exist
* `--module-name <NAME>` - stores a module-scope OBOM instead. The module is created inside the project if it does not exist yet
* `--module-id`, `--module-identifier` - address a module by the platform's own id, or by an identifier used verbatim

### Project scope is the normal case

Without any module option the OBOM is stored for the project as a whole, and that is usually what you want. A module is something that produces a deployment artefact -- which is why an SBOM and a SARIF report always have one. Infrastructure does not divide that way: a queue or a table belongs to no artefact at all, and a function may belong to one. Reaching for `--module-name` just to mirror the SBOM's module files the infrastructure under an artefact it is not part of.

Use `--module-name` only when the scanned sources really do describe one module's own infrastructure.

Uploading again for the same scope stores a new version, and a read returns the most recent one -- so two uploads for the same project scope do not add up, the second one wins. Scan the project root once rather than uploading per subdirectory.

### What the platform needs

* The `obom` feature has to be enabled for the company, otherwise both API routes answer `403`
* The API key needs a scope that allows uploads (developer, manager, compliance manager, portfolio manager, company security manager or company component manager)

### Exit codes

* `0` - the OBOM was stored
* `1` - the platform rejected the upload; its own messages are printed
* `2` - the file is not a CycloneDX OBOM, or a required option is missing

## User settings

Defaults are read from a TOML config file with profiles. The default location is `~/.ts-obom/config` and the file is created on first run with an empty `default` profile.

```toml
[default]
format = "ts"

[ci]
format = "ts"
verbose = true
```

* `ts-obom -p ci scan ...` selects the `ci` profile
* `ts-obom --config <path> scan ...` uses a different config file
* environment variables prefixed with `TS_OBOM_` override options, for example `TS_OBOM_SCAN_OUTPUT_PATH=obom.json` or `TS_OBOM_UPLOAD_API_KEY=...`, which is how a CI job passes the key without putting it on the command line
* a `tsproject.toml` in a scanned directory provides per-project defaults with the same keys

The prefix deliberately differs from ts-scan's `TS_` so that both tools can be configured side by side in the same CI job without one picking up the other's variables.

## Scan exit codes

* `0` - scan completed, including the case that no IAM grants were found
* `2` - usage error (no sources given, or `-f cyclonedx` with more than one source) or the vendored graph builder's dependencies are missing

## What the scan does not do

* It does not call any cloud API. Managed policies referenced by ARN (`arn:aws:iam::aws:policy/...`) are reported under `unresolved` rather than expanded.
* It does not run `terraform init` or `tofu init`. Remote modules are not downloaded; local modules are followed.
* It does not evaluate conditions, permission boundaries or SCPs. The graph is the declared intent, not the effective permission.
