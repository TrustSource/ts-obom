# Adding Features

We appreciate any kind of support in extending what ***ts-obom*** can see. The [roadmap](roadmap.md) shows where our own priorities lie; if you want something else, or want it sooner, contributions are welcome.

> [!IMPORTANT]
>
> Please read the [development guidelines](guidelines.md) before committing code. Most of them are the usual thing, but the rules about the vendored Checkov subset are specific to this repository and easy to get wrong.

## 1. Decide where to add

Four kinds of extension come up, and they live in different places.

| You want to | Add to | Notes |
|-------------|--------|-------|
| Support another IaC language (Kubernetes manifests, ARM/Bicep, Pulumi) | a new front-end in `ts_obom/obom.py`, registered in `FRONTENDS` | The heaviest of the four. It needs a graph builder for that language; see below |
| Recognise more resources or grants in a language already supported | the extraction functions in `ts_obom/obom.py` | The most common contribution, and the easiest |
| Improve how a resource appears in the CycloneDX document | `ts_obom/cyclonedx.py` | Component types, properties, dependency edges |
| Transfer results somewhere else | `ts_obom/api.py` and a command under `ts_obom/cli/` | Follow the conventions in ADR-007 |

## 2. Adding to an existing front-end

This is where most of the open work is. Three tables carry knowledge that is deliberately partial, because a wrong entry is worse than a missing one:

* `SAM_POLICY_TEMPLATE_ACTIONS` — the [AWS SAM policy templates](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-policy-templates.html) and the actions they expand to. A template that is not listed becomes an `unresolved` entry rather than a guess.
* `TF_COMPUTE_RESOURCE_TYPES`, `TF_POLICY_RESOURCE_TYPES`, `TF_ATTACHMENT_RESOURCE_TYPES` — which Terraform resources hold a policy, which can assume a role, and which attach one.
* `_component_types()` in `ts_obom/cyclonedx.py` — the mapping from an IaC resource type to a CycloneDX component type. An unmapped type keeps Checkov's blanket `application`, which is honest; guessing `data` for something that is not storage is not.

Adding an entry to any of these is a small, well-testable change. Add a fixture under `tests/fixtures/` that actually exercises it, and assert on what the scan produces rather than on the table.

## 3. Adding a front-end

A front-end is a function `(source_dir, **options) -> ObomResult` registered in `FRONTENDS`. It has to produce two things: the inventory of declared resources, and the access grants between them.

The two existing front-ends get their graph from the vendored Checkov subset, which already parses CloudFormation, SAM, Terraform and OpenTofu. If the language you want is one Checkov supports, adding it is mostly a matter of vendoring that front-end's graph manager and walking its vertices — see `NOTICE.md` in `src/ts_obom/_vendor/` for how the vendoring was done and how to re-sync it.

If the language is one Checkov does not support, a front-end may bring its own parser. It does not have to use the vendored graph builder; it only has to return an `ObomResult`.

Whichever way: a front-end must not require cloud credentials, network access or an `init` step. Scans run offline, and everything that would need an external lookup belongs in `unresolved` rather than in a call.

## 4. Touching the vendored Checkov subset

`src/ts_obom/_vendor/checkov/` is not ours. It is a trimmed copy of [Checkov](https://github.com/bridgecrewio/checkov) under the Apache License 2.0, and it carries deliberate, documented modifications.

If you have to change it:

1. Mark every edited line with a `ts-obom:` comment at the edit site.
2. Add the change to `src/ts_obom/_vendor/NOTICE.md`, in the section for the release it goes into. Apache-2.0 §4(b) requires the changes to be stated; the NOTICE is where we state them.
3. Prefer not changing it at all. Most things can be done in `ts_obom/` on top of what the vendored code returns — the CycloneDX output is built that way, by enriching Checkov's own exporter rather than editing it.

## 5. Before you open a pull request

* `pytest` passes on Python 3.10, 3.11 and 3.12 (CI runs all three)
* `pyright src` is clean
* `CHANGELOG.md` has an entry and the version in `pyproject.toml` is bumped per [semver](https://semver.org/)
* An architectural decision — a new component, a changed interface, a new dependency — has an ADR in [architecture.md](architecture.md)
