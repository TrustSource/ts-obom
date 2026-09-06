# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import json
import typing as t

import click

from io import StringIO
from pathlib import Path

from . import cli, msg
from .. import do_scan, ObomScan
from ..obom import CheckovNotInstalledError


@cli.command('scan', help='Scans a target for infrastructure-as-code and extracts its OBOM (IAM access graph)')
@cli.inout_default_options(_out=True, _fmt=True)
@cli.frontend_options
@click.option('--verbose', default=False, is_flag=True,
              help="Verbose mode")
@click.option('--tag', required=False, type=str,
              help="Project's tag in the VCS")
@click.option('--branch', required=False, type=str,
              help="Project's branch in the VCS")
@click.argument('sources',
                type=click.Path(exists=True, path_type=Path),
                nargs=-1)
def scan_obom(sources: t.List[Path],
              output_path: t.Optional[Path],
              scan_format: str,
              verbose: bool,
              tag: str,
              branch: str,
              **kwargs):
    if not sources:
        msg.fail('No sources given. Pass one or more directories containing IaC sources.')
        exit(2)

    try:
        scans = list(do_scan(sources, verbose=verbose, tag=tag, branch=branch, **kwargs))
    except CheckovNotInstalledError as err:
        msg.fail(str(err))
        exit(2)

    if scans:
        output_scans(scans, output_path, scan_format)


def output_scans(scans: t.List[ObomScan], path: t.Optional[Path], fmt: str = 'ts'):
    if path:
        with path.resolve().open('w') as fp:
            dump_scans(scans, fp, fmt)
    else:
        output = StringIO()
        dump_scans(scans, output, fmt)
        output.seek(0)
        print(output.read())


def dump_scans(scans: t.List[ObomScan], fp: t.TextIO, fmt: str):
    if fmt == 'ts':
        json.dump([s.to_dict() for s in scans], fp, indent=2)

    elif fmt == 'dot':
        fp.write(to_dot(scans))

    else:
        raise ValueError(f'Unsupported output format: {fmt}')


def to_dot(scans: t.List[ObomScan]) -> str:
    """Renders the access graphs as one Graphviz digraph, one cluster per scan."""

    def q(value: str) -> str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    lines = ['digraph obom {', '  rankdir=LR;', '  node [shape=box, fontname="Helvetica"];',
             '  edge [fontname="Helvetica", fontsize=10];']

    for index, scan in enumerate(scans):
        lines.append(f'  subgraph cluster_{index} {{')
        lines.append(f'    label={q(scan.module)};')
        for edge in scan.result.edges:
            style = '' if edge.effect.casefold() == 'allow' else ', color=red, style=dashed'
            label = '\\n'.join(edge.actions) if edge.actions else edge.effect
            lines.append(f'    {q(edge.principal)} -> {q(edge.resource)} '
                         f'[label={q(label)}, tooltip={q(edge.grantedVia)}{style}];')
        for item in scan.result.unresolved:
            lines.append(f'    {q(item.principal)} [style=dotted, tooltip={q(item.reason + ": " + item.detail)}];')
        lines.append('  }')

    lines.append('}')
    return '\n'.join(lines) + '\n'
