# Vendored code notice

`checkov/` in this directory is a trimmed subset of
[bridgecrewio/checkov](https://github.com/bridgecrewio/checkov), licensed
under the [Apache License 2.0](checkov/LICENSE) (included alongside this
notice, unmodified). Checkov's copyright is retained by Bridgecrew/Prisma
Cloud (Palo Alto Networks) and its contributors.

## Provenance

- Upstream source: `bridgecrewio/checkov`, version `3.3.15`
  (`checkov/version.py`), commit `2137e91a69bbcf73d9c672073a049ec4b48f85ff`
  (`upstream/main` on the fork used, 2026-08-27).
- Trimmed and adapted via
  [`jthDEV/checkov`](https://github.com/jthDEV/checkov), branch
  `feature/scan2graph-extraction` (`scan2graph/vendor_src/`), for use by
  `ts_obom.obom`.

## What was changed from upstream (Apache-2.0 §4(b))

- **Reduced file set.** Only the ~25 files that
  `checkov.cloudformation.graph_manager` / `checkov.terraform.graph_manager`
  / `checkov.common.graph.db_connectors.networkx` genuinely need at runtime
  are included, out of the full checkov source tree.
- **23 stub modules added**, replacing subsystems that are imported
  somewhere on that path but never called by it (check-registry,
  Bridgecrew-platform-integration, reporting, external-check-verification,
  module-download-over-network, and SCA/SAST output code). Each stub is a
  short, self-documenting file: a module-level `__getattr__` returning a
  `unittest.mock.MagicMock` for any attribute, with `__all__ = []` so
  checkov's own `from x import *` package-init pattern is a no-op. Their
  exact paths are listed in `jthDEV/checkov`'s
  `scan2graph/vendor_src/checkov/**/__init__.py` (docstring-tagged) and in
  that repo's commit history.
- **One real code change:** `common/util/json_utils.py`. Its
  `CustomJSONEncoder` is genuinely used (Terraform variable-rendering
  serialization) and could not be stubbed, but its `default()` method
  special-cased four types from stubbed subsystems
  (`Severity`, `ImageDetails`, SAST `MatchMetadata`/`DataFlow`/
  `MatchLocation`/`Point`, `PotentialSecret`) purely via `isinstance()`
  checks. Replaced those four imports with local, unreachable sentinel
  classes of the same names — the branches become dead code (no object our
  code path produces is ever an instance of them) rather than a crash.
- No other line-level edits to files that were kept.

## Why vendored instead of `pip install checkov`

See the module docstring in `ts_obom/obom.py` for the full
reasoning: the full `checkov` PyPI distribution's declared dependencies
conflict with ts-scan's own (`cyclonedx-python-lib`, `packageurl-python`,
`importlib-metadata`), and none of that weight turned out to be needed for
graph-building specifically.

## Re-syncing with upstream checkov

If checkov's graph-builder internals change upstream in a way this vendored
copy needs, re-run the trimming process from `jthDEV/checkov`'s
`feature/scan2graph-extraction` branch against the new upstream commit
(iteratively import `checkov.cloudformation.graph_manager` /
`checkov.terraform.graph_manager` from a fresh copy, copy in whatever's
reported missing, re-verify against `scan2graph/testdata/`) rather than
hand-patching this copy in place.

## Changes made in ts-obom (2026-09-06)

Beyond the trimming described above, ts-obom carries these edits, each marked
with a `ts-obom:` comment at the edit site:

- `terraform/tf_parser.py`: `parse_file()` and the directory listing in
  `_parse_directory()` also accept OpenTofu files (`.tofu`, `.tofu.json`); a
  `name.tofu` file shadows `name.tf` in the same directory, as OpenTofu 1.8+
  does.
- `terraform/graph_builder/utils.py`: `extract_module_dependency_path()`
  recognises `.tofu`, `.tofu.json`, `.tf.json` and `.hcl` module file names in
  nested-module paths instead of assuming `.tf`.
- `terraform/module_loading/module_finder.py`: module discovery also walks
  `.tofu` files.

## Changes made in ts-obom (2026-09-22)

The CycloneDX exporter was brought in from the same fork so that ts-obom's
Operations BOM is built by checkov's own code rather than by a re-implementation
of it. Five modules that the trimming had replaced with stubs were restored to
their real upstream source for this, and two were added:

- **Restored from stubs to the real upstream files:**
  `common/bridgecrew/severities.py`, `common/bridgecrew/check_type.py`,
  `common/sca/commons.py`, `common/output/common.py`, `common/output/record.py`.
  Each had been a stub package directory; it is now the upstream module of the
  same name.
- **Added from upstream:** `common/output/cyclonedx.py`,
  `common/output/cyclonedx_consts.py`.
- **Two line-level edits**, both marked with a `ts-obom:` comment at the edit
  site:
  - `common/output/cyclonedx.py` and `common/output/cyclonedx_consts.py` import
    `CheckType` from `common/bridgecrew/check_type.py` instead of from
    `common/output/report.py`, which merely re-exports it. `report.py` stays a
    stub that way, and with it its dependencies (`junit_xml`, `tabulate`,
    `termcolor`'s report use) stay out of ts-obom.
  - `common/output/cyclonedx_consts.py`: `DEFAULT_CYCLONE_SCHEMA_VERSION` raised
    from CycloneDX 1.4 to 1.6, and 1.5/1.6 added to `CYCLONE_SCHEMA_VERSION`.
    1.6 is the version TrustSource's OBOM API is specified against, and the
    component types an Operations BOM needs (`platform`, `data`) were only
    introduced in 1.5.

`checkov.common.output.report.Report` itself is **not** vendored. The exporter
reads five attributes off a report (`check_type`, `passed_checks`,
`skipped_checks`, `failed_checks`, `extra_resources`) and ts-obom hands it a
small stand-in carrying those (`ts_obom.cyclonedx._InventoryReport`), so
checkov's whole reporting subsystem stays out of the package.

This adds `cyclonedx-python-lib`, `packageurl-python` and `termcolor` to
ts-obom's dependencies. The conflict that motivated the vendoring in the first
place was with ts-scan's pins, and ts-obom has been a separate package since
0.1.0 (see ADR-001), so those two libraries are no longer a problem to depend
on.
