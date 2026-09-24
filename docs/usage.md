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
* `cyclonedx` - a CycloneDX 1.6 Operations BOM. This is the format the TrustSource platform stores, and the one [`ts-obom upload`](upload.md) sends. A CycloneDX document describes exactly one subject, so this format takes exactly one source directory:

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
* `--deployment <NAME>` - Names the deployment this OBOM describes: an environment (`DEV`, `PRD`) or a customer setup (`kunde1`). See [Deployments and parameters](deployments.md)
* `--tag <TAG>` - Stores the SCM tag `<TAG>` in the result
* `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the result
* `--verbose` - Enables verbose mode

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

## Next

* [Deployments and parameters](deployments.md) — describing one environment or customer setup rather than the sources' defaults
* [Result format](format.md) — what the two output formats contain
* [Transferring to TrustSource](upload.md) — uploading a CycloneDX OBOM to the platform
