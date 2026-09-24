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
                 frontends: t.Optional[t.List[str]] = None,
                 deployment: t.Optional[str] = None,
                 parameterSources: t.Optional[t.Dict[str, str]] = None):
        self.source = source
        self.result = result
        self.tag = tag
        self.branch = branch
        self.frontends = frontends or list(FRONTENDS)
        #: Which deployment this document describes -- an environment (``DEV``,
        #: ``PRD``) or a customer setup (``kunde1``). Naming one only means
        #: something together with the parameter values that distinguish it,
        #: which is what ``parameterSources`` records.
        self.deployment = deployment
        #: Per front-end, where the parameter values came from: a file name, or
        #: ``defaults`` when nothing was supplied and the scan therefore used
        #: whatever the templates declare as their own default.
        self.parameterSources = parameterSources or {}

    @property
    def parameterSource(self) -> str:
        """One string for the whole document.

        ``defaults`` exactly when no front-end got a parameter source -- the
        case in which two documents of different deployments are byte-identical
        and must not be compared. Otherwise every active front-end is named, so
        a half-parameterised scan cannot pass for a full one.
        """
        if not any(source != 'defaults' for source in self.parameterSources.values()):
            return 'defaults'
        return ','.join(f'{name}={self.parameterSources.get(name, "defaults")}'
                        for name in self.frontends)

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
        if self.deployment:
            doc['deployment'] = self.deployment
        doc['parameterSource'] = self.parameterSource
        doc['tool'] = {
            'name': 'ts-obom',
            'version': __version__,
            'frontends': self.frontends,
            'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        doc.update(self.result.to_dict())
        return doc


#: Per front-end, the CLI option holding its parameter source and the option
#: name the extractor expects. A front-end that is absent here has no way to
#: take external parameter values yet and always scans with the defaults.
FRONTEND_PARAMETER_OPTIONS: t.Dict[str, str] = {
    'cloudformation': 'parameters',
    'terraform': 'var_file',
}


def _frontend_options(name: str, kwargs: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Front-end specific options out of the flat CLI namespace.

    ``--terraform:var-file`` arrives as ``terraform_var_file`` and reaches
    ``extract_terraform`` as ``var_file``; the ``<name>_ignore`` flag is
    handled by the caller and never forwarded.
    """
    prefix = f'{name}_'
    return {
        key[len(prefix):]: value
        for key, value in kwargs.items()
        if key.startswith(prefix) and key != f'{name}_ignore' and value is not None
    }


def do_scan(paths: t.Iterable[Path], **kwargs: t.Any) -> t.Iterable[ObomScan]:
    """Runs the OBOM extraction for every path.

    :param paths: local directories (or files, whose parent directory is used)
    :param kwargs: ``<frontend>_ignore`` flags and front-end specific options as
        produced by the CLI, plus ``verbose``/``tag``/``branch``/``deployment``
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
        parameter_sources = {}
        for name in frontends:
            options = _frontend_options(name, kwargs)
            result.extend(FRONTENDS[name](str(source_dir), **options))
            source = options.get(FRONTEND_PARAMETER_OPTIONS.get(name, ''))
            parameter_sources[name] = Path(source).name if source else 'defaults'

        if result.resources:
            msg.good(f'OBOM extraction done: {len(result.resources)} resources, '
                     f'{len(result.edges)} grants, {len(result.unresolved)} unresolved.')
        else:
            msg.info('OBOM extraction found no IaC resources.')

        scan = ObomScan(source_dir, result,
                        tag=kwargs.get('tag'), branch=kwargs.get('branch'),
                        frontends=frontends,
                        deployment=kwargs.get('deployment'),
                        parameterSources=parameter_sources)

        # Naming a deployment without giving it parameter values produces a
        # document that differs from another deployment's only by its label --
        # the templates are the same, so the resources are the same. Saying so
        # once here is cheaper than the wrong conclusion drawn from it later.
        if scan.deployment and scan.parameterSource == 'defaults':
            msg.warn(f"Deployment '{scan.deployment}' was named but no parameter values "
                     'were supplied, so the scan used the templates\' own defaults. '
                     'Another deployment scanned the same way yields an identical '
                     'document; the result records this as parameterSource=defaults.')

        yield scan
