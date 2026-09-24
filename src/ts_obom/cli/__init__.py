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
    import ts_obom.cli.upload

    cli()


class CLI(click.Group):
    frontend_options: t.Callable[..., t.Any]
    inout_default_options: t.Callable[..., t.Any]
    api_default_options: t.Callable[..., t.Any]

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
    """Adds the ``--<frontend>:<option>`` switches, following ts-scan's
    ``--<package manager>:<option>`` convention."""
    from .. import FRONTENDS

    # Both apply a deployment's own values on top of what the sources declare
    # as their defaults, which is what makes a named deployment describe that
    # deployment rather than the templates.
    f = click.option('--cloudformation:parameters', 'cloudformation_parameters',
                     type=click.Path(exists=True, dir_okay=False, path_type=Path),
                     help='Applies a CloudFormation parameter file on top of the '
                          'template defaults ([{ParameterKey, ParameterValue}] or a '
                          'name/value mapping)')(f)

    f = click.option('--terraform:var-file', 'terraform_var_file',
                     type=click.Path(exists=True, dir_okay=False, path_type=Path),
                     help='Applies a .tfvars file on top of the variable defaults')(f)

    for name in FRONTENDS:
        f = click.option(f'--{name}:ignore', f'{name}_ignore',
                         default=False, is_flag=True,
                         help=f'Ignores {name} sources')(f)
    return f


def api_default_options(project_name=True, is_project_name_required=True):
    """Adds the TrustSource API options, same names and defaults as ts-scan's.

    The base URL carries the API version (``/v2``): the version belongs in one
    place, not repeated in every method path.
    """
    def _apply(f):
        if project_name:
            f = click.option('--project-name', 'project_name', type=str,
                             required=is_project_name_required,
                             help='Project name the OBOM belongs to')(f)

        f = click.option('--api-key', 'api_key', type=str, required=True,
                         help='TrustSource API Key')(f)

        f = click.option('--base-url', 'base_url', default='https://api.trustsource.io/v2',
                         show_default=True,
                         help='TrustSource API base URL, including the API version')(f)
        return f

    return _apply


def inout_default_options(_in: bool, _out: bool, _fmt: bool):
    def _apply(f):
        if _in:
            f = click.argument('path',
                               type=click.Path(exists=True, path_type=Path))(f)
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
cli.api_default_options = api_default_options

scan_formats = [
    'ts',
    'cyclonedx',
    'dot',
]

scan_format_default = 'ts'
