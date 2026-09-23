# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""
``ts-obom upload`` -- transfers a CycloneDX OBOM to the TrustSource platform.

Follows ts-scan's transfer command in shape (a file argument, ``--base-url`` /
``--api-key`` / ``--project-name``, profile and environment defaults) but has
only one transfer path: the platform stores OBOMs as CycloneDX and nothing else,
so there is no native-format upload next to a CycloneDX import the way there is
in ts-scan. A file produced with ``-f ts`` is therefore rejected here, locally,
with a pointer to ``-f cyclonedx`` -- not sent off to earn a 400.
"""

import json
import typing as t

import click

from pathlib import Path

from . import cli, msg
from .. import __version__
from ..api import TrustSourceAPI
from ..cyclonedx import BOM_TYPE_PROPERTY, BOM_TYPE_VALUE


@cli.command('upload', help='Transfers a CycloneDX OBOM to the TrustSource API')
@cli.inout_default_options(_in=True, _out=False, _fmt=False)
@cli.api_default_options()
@click.option('--module-name', 'moduleName', type=str,
              help='Module name. Naming a module stores a module-scope OBOM; '
                   'the module is created in the project if it does not exist yet')
@click.option('--module-id', 'moduleId', type=str,
              help="Module id, if you know the platform's own id for it")
@click.option('--module-identifier', 'moduleIdentifier', type=str,
              help='Module identifier, used verbatim')
def upload_obom(path: Path,
                base_url: str,
                api_key: str,
                project_name: str,
                **kwargs):

    document = _load_obom(path)

    params = {k: v for k, v in kwargs.items() if v}
    params['projectName'] = project_name
    # Provenance, stored by the platform next to the document.
    params['toolName'] = 'ts-obom'
    params['toolVersion'] = __version__

    scope = 'module' if any(kwargs.values()) else 'project'
    msg.info(f'Uploading the OBOM ({len(document.get("components") or [])} components, '
             f'{scope} scope)...')

    api = TrustSourceAPI(base_url, api_key)

    try:
        result = api.import_obom(path, params)
    except TrustSourceAPI.Error as err:
        _fail(err)
        return

    stored_scope = result.get('scope', scope)
    ids = ', '.join(f'{k}={result[k]}' for k in ('projectId', 'moduleId') if result.get(k))
    msg.good(f'OBOM stored ({stored_scope} scope, {ids})')


def _load_obom(path: Path) -> t.Dict[str, t.Any]:
    """Reads the document and checks locally what the platform checks remotely.

    Every rejection below is one the API would produce too; catching them here
    turns a 400 from a CI step into a message naming the flag that fixes it.
    """
    try:
        with path.open('r') as fp:
            document = json.load(fp)
    except json.JSONDecodeError as err:
        msg.fail(f'{path} is not valid JSON: {err}')
        exit(2)

    if isinstance(document, list):
        msg.fail(f'{path} holds a list of scan results, which is the "ts" output format. '
                 'The platform stores OBOMs as CycloneDX: re-run the scan with '
                 '-f cyclonedx and upload that file.')
        exit(2)

    if not isinstance(document, dict) or document.get('bomFormat') != 'CycloneDX':
        msg.fail(f'{path} is not a CycloneDX document. Re-run the scan with -f cyclonedx.')
        exit(2)

    properties = (document.get('metadata') or {}).get('properties') or []
    if not any(p.get('name') == BOM_TYPE_PROPERTY and p.get('value') == BOM_TYPE_VALUE
               for p in properties if isinstance(p, dict)):
        msg.fail(f'{path} is a CycloneDX document but carries no '
                 f'{BOM_TYPE_PROPERTY}={BOM_TYPE_VALUE} marker in metadata.properties, '
                 'so the platform would not accept it as an OBOM.')
        exit(2)

    return document


#: What the platform's own answers mean, so a CI log says what to do rather than
#: just which number came back.
_HINTS = {
    400: 'The platform rejected the document.',
    401: 'The API key was not accepted.',
    403: 'Either the API key scope is too limited, or the OBOM feature is not '
         'enabled for this company.',
    404: 'The project or module could not be resolved. The project must already '
         'exist; only a module is created on the fly.',
    502: 'The OBOM service could not be reached by the platform.',
    503: 'The OBOM service is not configured for this installation.',
}


def _fail(err: TrustSourceAPI.Error):
    msg.fail('Upload failed')
    if hint := _HINTS.get(err.status_code or 0):
        msg.fail(hint)
    msg.fail(text=str(err))
    for message in err.messages:
        msg.fail(text=f'  - {message}')
    exit(1)
