# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import typing as t

from datetime import datetime, timezone
from pathlib import Path

from . import obom


def _get_version_from_metadata(default: str = '0.0.0') -> str:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except Exception:
        return default

    for name in ('ts-obom', 'ts_obom', __name__):
        try:
            return version(name)
        except PackageNotFoundError:
            continue
        except Exception:
            continue

    return default


__version__ = _get_version_from_metadata()


#: IaC front-ends the scanner knows, keyed by the CLI option prefix
#: (``--cloudformation:ignore``, ``--terraform:ignore``).
FRONTENDS: t.Dict[str, t.Callable[[str], obom.ObomResult]] = {
    'cloudformation': obom.extract_cloudformation,
    'terraform': obom.extract_terraform,
}


class ObomScan:
    """One OBOM extraction result for one scanned source directory.

    Mirrors the shape of ts-scan's ``DependencyScan`` header (module,
    moduleId, source, tag, branch) so that results can later be handled by
    the same tooling, followed by the access graph itself.
    """

    def __init__(self, source: Path, result: obom.ObomResult,
                 tag: t.Optional[str] = None, branch: t.Optional[str] = None,
                 frontends: t.Optional[t.List[str]] = None):
        self.source = source
        self.result = result
        self.tag = tag
        self.branch = branch
        self.frontends = frontends or list(FRONTENDS)

    @property
    def module(self) -> str:
        return self.source.name or str(self.source)

    @property
    def moduleId(self) -> str:
        return f'obom:{self.module}'

    def to_dict(self) -> t.Dict[str, t.Any]:
        doc: t.Dict[str, t.Any] = {
            'module': self.module,
            'moduleId': self.moduleId,
            'source': str(self.source),
        }
        if self.tag:
            doc['tag'] = self.tag
        if self.branch:
            doc['branch'] = self.branch
        doc['tool'] = {
            'name': 'ts-obom',
            'version': __version__,
            'frontends': self.frontends,
            'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        doc.update(self.result.to_dict())
        return doc


def do_scan(paths: t.Iterable[Path], **kwargs: t.Any) -> t.Iterable[ObomScan]:
    """Runs the OBOM extraction for every path.

    :param paths: local directories (or files, whose parent directory is used)
    :param kwargs: ``<frontend>_ignore`` flags as produced by the CLI, plus
        ``verbose``/``tag``/``branch``
    :return: an iterable over scan results, one per path
    """
    from .cli import msg

    frontends = [
        name for name in FRONTENDS
        if not kwargs.get(f'{name}_ignore', False)
    ]

    if not frontends:
        msg.warn('All IaC front-ends are disabled, nothing to scan.')
        return

    obom.require_checkov()

    for path in paths:
        path = path.resolve()
        source_dir = path if path.is_dir() else path.parent

        msg.info(f'Extracting OBOM from IaC sources in {source_dir}...')

        result = obom.ObomResult()
        for name in frontends:
            result.extend(FRONTENDS[name](str(source_dir)))

        if result.resources:
            msg.good(f'OBOM extraction done: {len(result.resources)} resources, '
                     f'{len(result.edges)} grants, {len(result.unresolved)} unresolved.')
        else:
            msg.info('OBOM extraction found no IaC resources.')

        yield ObomScan(source_dir, result,
                       tag=kwargs.get('tag'), branch=kwargs.get('branch'),
                       frontends=frontends)
