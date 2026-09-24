# Transferring to TrustSource

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

## Options

* `--api-key <KEY>` - TrustSource API key. Sent as the `x-api-key` header, never in the body or the URL
* `--base-url <URL>` - API base URL **including the API version**, default `https://api.trustsource.io/v2`. The version lives here and nowhere else, so pointing at another version or another installation is one option
* `--project-name <NAME>` - the project the OBOM belongs to. The project must already exist
* `--module-name <NAME>` - stores a module-scope OBOM instead. The module is created inside the project if it does not exist yet
* `--module-id`, `--module-identifier` - address a module by the platform's own id, or by an identifier used verbatim

## Project scope is the normal case

Without any module option the OBOM is stored for the project as a whole, and that is usually what you want. A module is something that produces a deployment artefact -- which is why an SBOM and a SARIF report always have one. Infrastructure does not divide that way: a queue or a table belongs to no artefact at all, and a function may belong to one. Reaching for `--module-name` just to mirror the SBOM's module files the infrastructure under an artefact it is not part of.

Use `--module-name` only when the scanned sources really do describe one module's own infrastructure.

Uploading again for the same scope stores a new version, and a read returns the most recent one -- so two uploads for the same project scope do not add up, the second one wins. Scan the project root once rather than uploading per subdirectory.

## What the platform needs

* The `obom` feature has to be enabled for the company, otherwise both API routes answer `403`
* The API key needs a scope that allows uploads (developer, manager, compliance manager, portfolio manager, company security manager or company component manager)

## Exit codes

* `0` - the OBOM was stored
* `1` - the platform rejected the upload; its own messages are printed
* `2` - the file is not a CycloneDX OBOM, or a required option is missing

