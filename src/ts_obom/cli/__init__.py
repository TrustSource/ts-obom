# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import click
import typing as t
import toml

from wasabi.printer import Printer
from pathlib import Path

_default_config_location = '~/.ts-obom/config'

msg = Printer(line_max=240, colors={'info': 'cyan'})


def start():
    import ts_obom.cli.scan

    cli()


class CLI(click.Group):
    frontend_options: t.Callable[..., t.Any]
    inout_default_options: t.Callable[..., t.Any]

    def invoke(self, ctx):
        ctx.obj = {
            'args': ctx.args
        }
        super().invoke(ctx)


@click.group(cls=CLI, context_settings={'auto_envvar_prefix': 'TS_OBOM'})
@click.version_option(package_name='ts-obom')
@click.option('--config',
              default=Path(_default_config_location),
              type=click.Path(path_type=Path, dir_okay=False))
@click.option('-p', '--profile', default='default', type=str)
@click.pass_context
def cli(ctx, config: Path, profile: str):
    cfg_path = config.expanduser().resolve(strict=False)

    if not cfg_path.exists():
        cfg_path = _create_default_config(cfg_path)

    cfg_data = toml.load(cfg_path)

    ctx.obj['config'] = cfg_data
    ctx.obj['config_path'] = cfg_path

    defaults = cfg_data.get(profile)

    if defaults is None:
        msg.fail(f"Profile '{profile}' not found in the config file.")
        exit(1)

    ctx.default_map = defaults

    for sub in ctx.command.commands.values():
        sub.context_settings['default_map'] = defaults

    if args := ctx.obj['args']:
        for arg in args:
            candidate = Path(arg)
            if candidate.is_dir() and (proj_cfg := _load_project_config(candidate)):
                ctx.default_map.update(proj_cfg)
                break


def _create_default_config(cfg_path: Path) -> Path:
    cfg = {
        'default': {}
    }

    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

        with cfg_path.open('w') as fp:
            fp.write(toml.dumps(cfg))

    return cfg_path


def _load_project_config(path: Path) -> dict:
    cfg_path = path / 'tsproject.toml'
    if cfg_path.exists():
        return toml.load(cfg_path)

    return {}


def frontend_options(f):
    """Adds ``--<frontend>:ignore`` flags, following ts-scan's
    ``--<package manager>:<option>`` convention."""
    from .. import FRONTENDS

    for name in FRONTENDS:
        f = click.option(f'--{name}:ignore', f'{name}_ignore',
                         default=False, is_flag=True,
                         help=f'Ignores {name} sources')(f)
    return f


def inout_default_options(_out: bool, _fmt: bool):
    def _apply(f):
        if _out:
            f = click.option('-o', '--output', 'output_path',
                             type=click.Path(path_type=Path),
                             required=False,
                             help='Output path for the scan')(f)
        if _fmt:
            f = click.option('-f', '--format', 'scan_format',
                             type=click.Choice(choices=scan_formats),
                             default=scan_format_default,
                             help='Scans file format')(f)
        return f

    return _apply


cli.frontend_options = frontend_options
cli.inout_default_options = inout_default_options

scan_formats = [
    'ts',
    'dot',
]

scan_format_default = 'ts'
