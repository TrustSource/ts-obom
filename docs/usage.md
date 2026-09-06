# Usage

***ts-obom*** follows the command conventions of ***ts-scan***: verbs as sub-commands, `-o/--output` and `-f/--format` for results, `--<front-end>:<option>` for front-end specific switches, a profile based config file and an optional `tsproject.toml` in the scanned directory. If you know ts-scan, ts-obom will feel familiar.

## Scan

The **scan** command searches one or more directories for infrastructure-as-code sources, builds the resource graph and extracts the IAM access grants.

```shell
ts-obom scan -o <path to the output file> [-f <output format>] <path to one or more directories>
```

Every directory produces one result document. Directories are scanned recursively by the IaC front-ends; a file argument is treated as its parent directory.

The `-f <output format>` option controls the output format and can be:

* `ts` - the TrustSource OBOM JSON format (default), see [Result format](format.md)
* `dot` - a Graphviz digraph, one cluster per scanned directory. Render it with Graphviz, for example:

```shell
ts-obom scan -f dot ./infrastructure | dot -Tsvg -o obom.svg
```

Without `-o` the result is printed to standard output.

### Options

Front-end specific options are prefixed with the front-end name, like package manager options in ts-scan:

* `--cloudformation:ignore` - Skip CloudFormation and AWS SAM templates
* `--terraform:ignore` - Skip Terraform sources

General options:

* `--tag <TAG>` - Stores the SCM tag `<TAG>` in the result
* `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the result
* `--verbose` - Enables verbose mode

The full list of options can be printed using:

```shell
ts-obom scan --help
```

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
* environment variables prefixed with `TS_OBOM_` override options, for example `TS_OBOM_SCAN_OUTPUT_PATH=obom.json`
* a `tsproject.toml` in a scanned directory provides per-project defaults with the same keys

The prefix deliberately differs from ts-scan's `TS_` so that both tools can be configured side by side in the same CI job without one picking up the other's variables.

## Exit codes

* `0` - scan completed, including the case that no IAM grants were found
* `2` - usage error (no sources given) or the vendored graph builder's dependencies are missing

## What the scan does not do

* It does not call any cloud API. Managed policies referenced by ARN (`arn:aws:iam::aws:policy/...`) are reported under `unresolved` rather than expanded.
* It does not run `terraform init`. Remote modules are not downloaded; local modules are followed.
* It does not evaluate conditions, permission boundaries or SCPs. The graph is the declared intent, not the effective permission.
