import json
import re
from pathlib import Path

from click.testing import CliRunner

import ts_obom
import ts_obom.cli.scan  # noqa: F401  registers the scan command, as start() does
from ts_obom.cli import cli

FIXTURES = Path(__file__).parent / 'fixtures'


def _json_payload(output: str):
    """The scan prints progress messages first; the document starts at the line holding '['."""
    match = re.search(r'(?m)^\[$', output)
    assert match, output
    return json.loads(output[match.start():])


def _run(tmp_path, *args):
    runner = CliRunner()
    config = tmp_path / 'config'
    return runner.invoke(cli, ['--config', str(config), *args], catch_exceptions=False)


def test_scan_writes_ts_document_per_source(tmp_path):
    out = tmp_path / 'obom.json'

    result = _run(tmp_path, 'scan', '-o', str(out), '--tag', 'v1', '--branch', 'main',
                  str(FIXTURES / 'cloudformation'), str(FIXTURES / 'terraform'))

    assert result.exit_code == 0, result.output
    docs = json.loads(out.read_text())
    assert [d['module'] for d in docs] == ['cloudformation', 'terraform']
    assert docs[0]['moduleId'] == 'obom:cloudformation'
    assert docs[0]['tag'] == 'v1' and docs[0]['branch'] == 'main'
    assert docs[0]['tool']['name'] == 'ts-obom'
    assert docs[0]['tool']['version'] == ts_obom.__version__
    assert docs[0]['tool']['frontends'] == ['cloudformation', 'terraform']
    assert docs[0]['edges'] and docs[1]['edges']


def test_scan_prints_to_stdout_without_output_option(tmp_path):
    result = _run(tmp_path, 'scan', str(FIXTURES / 'terraform'))

    assert result.exit_code == 0, result.output
    docs = _json_payload(result.output)
    assert docs[0]['module'] == 'terraform'


def test_frontend_ignore_options_follow_ts_scan_convention(tmp_path):
    result = _run(tmp_path, 'scan', '--cloudformation:ignore', str(FIXTURES / 'cloudformation'))

    assert result.exit_code == 0, result.output
    docs = _json_payload(result.output)
    assert docs[0]['tool']['frontends'] == ['terraform']
    assert docs[0]['edges'] == []

    result = _run(tmp_path, 'scan', '--cloudformation:ignore', '--terraform:ignore',
                  str(FIXTURES / 'terraform'))
    assert result.exit_code == 0
    assert 'nothing to scan' in result.output


def test_dot_format_renders_graphviz(tmp_path):
    out = tmp_path / 'obom.dot'

    result = _run(tmp_path, 'scan', '-f', 'dot', '-o', str(out), str(FIXTURES / 'terraform'))

    assert result.exit_code == 0, result.output
    dot = out.read_text()
    assert dot.startswith('digraph obom {')
    assert 'subgraph cluster_0' in dot
    assert '"arn:aws:s3:::orderdesk-exports/*"' in dot
    assert 's3:GetObject' in dot


def test_scan_without_sources_fails(tmp_path):
    result = _run(tmp_path, 'scan')
    assert result.exit_code == 2
    assert 'No sources given' in result.output
