# Development Guidelines

We appreciate every contribution to ***ts-obom***. The following is what makes a commit easy to accept — none of it is unusual, but the rules about the vendored code are specific to this repository.

Feel free to reach out and discuss, or to suggest better practice. If any statement here looks wrong to you, it might be.

## Standards

We follow [PEP 8](https://peps.python.org/pep-0008/). Type hints are used throughout and `pyright src` is expected to be clean; CI runs it.

## Comments say why, not what

The code says what it does. A comment that repeats it in prose ages badly and hides the ones that matter. What is worth writing down is the reason a thing is the way it is — the constraint that forced it, the alternative that was tried, the failure mode being avoided. Several of the trickier parts of this codebase are only understandable through those comments, which is deliberate.

## Tests are confirmatory *and* adversarial

A confirmatory test shows the change does what you intended. An adversarial one tries to break it anyway: the absent field, the malformed value, the duplicate entry, the caller that does not follow the happy path. Both are expected, not one or the other.

For this tool specifically, the adversarial cases that keep coming up are IaC sources that do not parse, references that resolve to nothing, and parameter values for things that do not exist. None of those may crash a scan, and none may silently disappear either — they belong in `unresolved`.

## Never guess

The scan reports what the sources declare. Where it cannot resolve something — a managed policy ARN whose contents live in AWS, a SAM policy template we do not know — the answer is an `unresolved` entry, not an approximation. A reviewer can work with a gap they can see; they cannot work with a plausible-looking value that is wrong.

The same applies to mappings: an unmapped resource type keeps its generic component type rather than being sorted into the nearest-looking bucket.

## Decisions get an ADR

New components, changed interfaces, new dependencies and reversals of earlier choices are recorded as an ADR in [architecture.md](architecture.md), with context, decision and consequences. Superseded ADRs are marked as superseded, never deleted — the old reasoning is usually the most valuable part.

## Versioning and changelog

[Semantic versioning](https://semver.org/), and a [Keep a Changelog](https://keepachangelog.com/) entry in `CHANGELOG.md` with every user-visible change. The version lives in `pyproject.toml` and is reported by `ts-obom --version`, so it is always possible to tell which release produced a given document.

## The vendored Checkov subset

`src/ts_obom/_vendor/checkov/` is a trimmed copy of [Checkov](https://github.com/bridgecrewio/checkov), Apache-2.0, not our code. Two rules:

* Every edit is marked with a `ts-obom:` comment at the edit site **and** listed in `src/ts_obom/_vendor/NOTICE.md`. Apache-2.0 §4(b) requires stating the changes; that file is where we state them.
* Prefer building on top of it to editing it. The CycloneDX output works that way — Checkov's own exporter produces the document and `ts_obom/cyclonedx.py` enriches the result — which keeps re-syncing with upstream possible.

## Offline by default

A scan reads files. It does not call a cloud API, does not run `terraform init`, and does not download modules. Anything that would need an external lookup is reported as unresolved instead. Keeping that true is what lets the tool run in a build container without credentials.
