# Deployments and parameters

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

## Parameter files

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

## Why a name alone is not enough

This is the one thing to understand about deployments, so it is worth stating twice: the graph is built from the sources, and the sources declare defaults. `!Sub 'arn:aws:s3:::${BucketName}/*'` over a parameter whose `Default` is `orderdesk-dev-reports` comes out as `arn:aws:s3:::orderdesk-dev-reports/*` — a concrete value that belongs to no deployment in particular.

Two scans of the same sources therefore produce **byte-identical documents**. Naming one `DEV` and the other `PRD` would make them look comparable and show no difference, which is an artefact of how they were produced rather than a statement about the deployments.

`parameterSource` exists so that this is visible in the document instead of having to be remembered. A consumer comparing two OBOMs can check it first and refuse to draw a conclusion from two documents that both say `defaults`.

## What this is for

Once two deployments are described from their own parameter values, the questions worth asking become answerable: what does production have that development does not, which customer setup grants a role something the others do not, and does a finding exist everywhere or only in one place.

Holding them side by side is the platform's part of the job; the scanner's part is making sure the documents genuinely differ where the deployments differ.
