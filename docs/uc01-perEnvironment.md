# Use Case #01 — One OBOM per environment, from the pipeline

The most useful thing ***ts-obom*** does is not producing a single document. It is producing one per deployment, from the same sources, so that the differences between environments stop being folklore.

## Why you would want this

Infrastructure diverges quietly. A role gets an extra permission in production during an incident and nobody removes it. A customer setup is cloned and then edited. A queue exists in development and was never created in production, so a grant points at nothing.

None of that shows up in a code review, because the code is identical — the difference lives in the parameter files. It shows up when you put two OBOMs of the same project side by side and ask what changed.

The same evidence answers the question a threat model needs: which identity may touch which resource, **in the environment that actually matters**.

## Prerequisites

* ***ts-obom*** installed in the pipeline (`pip install ts-obom`, or the `trustsource/ts-obom` image)
* One parameter file per environment — which you very likely already have, because that is how the deployment works
* A TrustSource API key with upload permission, and the `obom` feature enabled for the company, if you want the results on the platform

## The shape of it

The pattern most repositories already follow is one template and one parameter file per environment: `deploy2DEV.sh` and `deploy2PRD.sh` feeding `params4DEV.json` and `params4PRD.json` into the same stack. That is exactly what ts-obom wants — it reads the same parameter file the deployment reads.

```shell
ts-obom scan -f cyclonedx \
  --deployment DEV \
  --cloudformation:parameters params4DEV.json \
  -o obom-dev.cdx.json .

ts-obom upload --api-key "$TS_API_KEY" --project-name Orderdesk obom-dev.cdx.json
```

and the same again for production:

```shell
ts-obom scan -f cyclonedx \
  --deployment PRD \
  --cloudformation:parameters params4PRD.json \
  -o obom-prd.cdx.json .

ts-obom upload --api-key "$TS_API_KEY" --project-name Orderdesk obom-prd.cdx.json
```

Scan the **project root**, not single subdirectories: the front-ends recurse, so one run covers every template below it. For Terraform and OpenTofu the equivalent flag is `--terraform:var-file params4PRD.tfvars`.

## In a GitHub Actions workflow

```yaml
- name: OBOM per environment
  run: |
    pip install ts-obom
    for env in DEV PRD; do
      ts-obom scan -f cyclonedx \
        --deployment "$env" \
        --cloudformation:parameters "params4${env}.json" \
        -o "obom-${env}.cdx.json" .
      ts-obom upload \
        --api-key "${{ secrets.TS_API_KEY }}" \
        --project-name Orderdesk \
        "obom-${env}.cdx.json"
    done
```

The key goes in as a secret and travels as the `x-api-key` header — never in the body, never in the URL.

## The one mistake to avoid

Naming a deployment without giving it that deployment's parameter values.

```shell
# Don't do this
ts-obom scan -f cyclonedx --deployment PRD -o obom-prd.cdx.json .
```

The scan resolves references against the **defaults declared in the sources**, so this produces exactly the same document as the same command with `--deployment DEV`. Side by side they would show no difference, which says nothing about the environments and everything about how the documents were made.

ts-obom warns when you do it, and records `parameterSource: defaults` in the result so that a reader can see it later. Two documents that both say `defaults` are not comparable, however they are named. See [Deployments and parameters](deployments.md).

## What you get

On the platform, one OBOM per deployment of the project, each in its latest version, listed side by side. Locally, two CycloneDX documents that a diff already makes useful — the component lists, the grant properties and the dependency edges all differ where the deployments differ, and nowhere else.
