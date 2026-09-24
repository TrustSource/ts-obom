# ts-obom Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-09-24

### New Features
    * `--cloudformation:parameters <FILE>` applies a CloudFormation parameter file on top of the
      templates' declared defaults, so a CloudFormation scan describes one concrete deployment
      instead of whatever the templates default to. Reads TrustSource's own
      `[{ParameterKey, ParameterValue}]` format -- the one the deploy scripts feed to
      `sam deploy --parameter-overrides` -- as well as a flat name/value mapping, told apart by
      the parsed shape rather than by a flag
    * A value supplied for a parameter that no scanned template declares is reported under
      `unresolved` with the reason `unused-parameter`, instead of being silently ignored. It is
      usually a typo or the wrong file, and ignoring it would let `parameterSource` claim more
      than the scan actually applied

### Improvements
    * With this, both front-ends can be parameterised, so `parameterSource` can name a real source
      for a whole scan (`cloudformation=params4PRD.json,terraform=params4PRD.tfvars`) and two
      deployments of one project are genuinely comparable

## [0.3.0] - 2026-09-24

### New Features
    * `--deployment <NAME>` names the deployment an OBOM describes -- an environment (`DEV`, `PRD`)
      or a customer setup (`kunde1`) -- so several deployments of one project can be held side by
      side and compared. The name is a property of the document
      (`trustsource:obom:deployment`), not an upload parameter, so what the CLI was given is what
      the document says (ADR-009)
    * `--terraform:var-file <FILE>` applies a `.tfvars` file on top of the variable defaults, the
      way `terraform -var-file` does, so a named deployment actually describes that deployment's
      values instead of the sources' defaults
    * Every result records `parameterSource`, never omitted: `defaults`, or `<front-end>=<file>`
      per active front-end. Two documents that both say `defaults` are byte-identical whatever
      they are named, and a reader can now see that instead of concluding "no drift"
    * The CycloneDX document declares `metadata.lifecycles: [{phase: operations}]` -- CycloneDX's
      own way of saying this is an Operations BOM, next to the TrustSource marker

### Improvements
    * Naming a deployment without supplying parameter values is warned about twice: when the scan
      produces such a document, and again when `ts-obom upload` is about to send it
    * `ts-obom upload` names the deployment it is transferring, read back out of the document
      rather than taken as an option, so the two cannot contradict each other

### Known limitations
    * CloudFormation cannot take parameter values yet -- checkov's parser accepts no external
      parameter file, so a CloudFormation scan always records `parameterSource=defaults`. Support
      for TrustSource's own `[{ParameterKey, ParameterValue}]` files is the next step (ADR-009)

## [0.2.0] - 2026-09-22

### New Features
    * `-f cyclonedx` writes the scan result as a CycloneDX 1.6 **Operations BOM**, the format the
      TrustSource OBOM API accepts: every resource declared in the scanned sources becomes a
      component, the IAM grants become component properties and `dependencies` edges, and
      `metadata.properties` carries the `trustsource:bomType = obom` marker the platform requires
    * `ts-obom upload` transfers a CycloneDX OBOM to `POST /core/imports/scan/obom`, following
      ts-scan's transfer command: `--base-url` (API version included, default
      `https://api.trustsource.io/v2`), `--api-key` (sent as the `x-api-key` header),
      `--project-name` and `--module-name` / `--module-id` / `--module-identifier` for the scope.
      A rejection by the platform is reported with its own messages and a non-zero exit code
    * The scan result now carries a `resources` list -- the full inventory of declared resources,
      not only the identities holding an IAM grant. This is what the Operations BOM is made of, and
      it is part of the native `ts` format as well

### Improvements
    * The CycloneDX document is produced by Checkov's own exporter, vendored from the same fork as
      the graph builder, so component identity (the `pkg:<front-end>/...@sha1:<file hash>` purl)
      matches what `checkov -o cyclonedx_json` produces for the same sources. See
      `src/ts_obom/_vendor/NOTICE.md` for what that added to the vendored subset
    * Resource types are mapped to CycloneDX component types where the mapping is unambiguous
      (`platform` for compute, `container` for task definitions and images, `data` for storage,
      queues and secrets); unmapped types keep Checkov's `application`
    * `ts-obom upload` refuses a file in the native `ts` format locally, naming `-f cyclonedx`,
      instead of letting the platform answer with a 400

### Fixed
    * The documentation described the OBOM as an *Ownership* Bill of Materials and stated that it
      does not overlap with a CycloneDX OBOM. That was a scope error: TrustSource's OBOM is an
      **Operations** Bill of Materials throughout the platform, and the scanner now produces one.
      The access graph is kept -- as an enrichment of the inventory, not as the document itself

## [0.1.0] - 2026-09-06

### New Features
    * Initial release as a standalone tool, extracted from the `obom` branch of ts-scan
    * `ts-obom scan` extracts IAM access grants from CloudFormation / AWS SAM templates and Terraform / OpenTofu sources into the TrustSource OBOM JSON format
    * OpenTofu `.tofu` and `.tofu.json` files are scanned by the `terraform` front-end, honouring OpenTofu's rule that a `.tofu` file shadows a `.tf` file of the same name
    * `-f dot` renders the access graph as a Graphviz digraph
    * `--cloudformation:ignore` and `--terraform:ignore` switch individual IaC front-ends off, following ts-scan's option conventions
    * Profile-based config file (`~/.ts-obom/config`), `tsproject.toml` project defaults and `TS_OBOM_` environment variables
    * Docker image `trustsource/ts-obom` and PyPI package `ts-obom`, released from version tags

### Improvements
    * The vendored Checkov graph-builder subset ships with its Apache-2.0 LICENSE and a NOTICE documenting provenance and changes
