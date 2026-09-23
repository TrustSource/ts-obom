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

* `--tag <TAG>` - Stores the SCM tag `<TAG>` in the result
* `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the result
* `--verbose` - Enables verbose mode

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
