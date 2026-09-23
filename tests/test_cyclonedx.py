import json
from pathlib import Path

from click.testing import CliRunner

import ts_obom
import ts_obom.cli.scan  # noqa: F401  registers the scan command, as start() does
from ts_obom.cli import cli
from ts_obom.cyclonedx import BOM_TYPE_PROPERTY, BOM_TYPE_VALUE

FIXTURES = Path(__file__).parent / 'fixtures'


def _scan_cyclonedx(tmp_path, *sources, extra=()):
    out = tmp_path / 'obom.cdx.json'
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ['--config', str(tmp_path / 'config'), 'scan', '-f', 'cyclonedx', '-o', str(out),
         *extra, *[str(s) for s in sources]],
        catch_exceptions=False)
    return result, out


def _properties(document, name):
    return [p['value'] for p in document['metadata'].get('properties', [])
            if p['name'] == name]


def test_cyclonedx_document_is_accepted_shaped(tmp_path):
    result, out = _scan_cyclonedx(tmp_path, FIXTURES / 'cloudformation')
    assert result.exit_code == 0, result.output

    document = json.loads(out.read_text())

    # Exactly the three things ts-obom-ingest checks before it stores anything.
    assert document['bomFormat'] == 'CycloneDX'
    assert document['specVersion']
    assert _properties(document, BOM_TYPE_PROPERTY) == [BOM_TYPE_VALUE]


def test_cyclonedx_lists_every_declared_resource(tmp_path):
    _, out = _scan_cyclonedx(tmp_path, FIXTURES / 'cloudformation')
    document = json.loads(out.read_text())

    names = {component['name'] for component in document['components']}
    assert names == {
        'AWS::DynamoDB::Table.OrdersTable',
        'AWS::IAM::Role.ReportRole',
        'AWS::Serverless::Function.OrderApiFunction',
    }, 'the inventory is every resource, not only the ones holding IAM grants'

    types = {component['name']: component['type'] for component in document['components']}
    assert types['AWS::Serverless::Function.OrderApiFunction'] == 'platform'
    assert types['AWS::DynamoDB::Table.OrdersTable'] == 'data'
    # Unmapped resource types keep checkov's own blanket type rather than a guess.
    assert types['AWS::IAM::Role.ReportRole'] == 'application'


def test_cyclonedx_carries_grants_and_module_metadata(tmp_path):
    _, out = _scan_cyclonedx(tmp_path, FIXTURES / 'cloudformation',
                             extra=('--tag', 'v2.4.17', '--branch', 'main'))
    document = json.loads(out.read_text())

    assert document['metadata']['component']['name'] == 'cloudformation'
    assert _properties(document, 'trustsource:obom:tag') == ['v2.4.17']
    assert _properties(document, 'trustsource:obom:branch') == ['main']

    tools = {tool['name'] for tool in document['metadata']['tools']}
    assert 'ts-obom' in tools and 'checkov' in tools

    function = next(c for c in document['components']
                    if c['name'] == 'AWS::Serverless::Function.OrderApiFunction')
    grants = [json.loads(p['value']) for p in function['properties']
              if p['name'] == 'trustsource:obom:grant']
    assert any('dynamodb:PutItem' in grant['actions'] for grant in grants)
    assert any(grant['grantedVia'].startswith('SAM policy template') for grant in grants)


def test_cyclonedx_links_a_grant_to_the_resource_it_names(tmp_path):
    _, out = _scan_cyclonedx(tmp_path, FIXTURES / 'cloudformation')
    document = json.loads(out.read_text())

    by_name = {c['name']: c['bom-ref'] for c in document['components']}
    function_ref = by_name['AWS::Serverless::Function.OrderApiFunction']
    table_ref = by_name['AWS::DynamoDB::Table.OrdersTable']

    dependencies = {d['ref']: d.get('dependsOn', []) for d in document['dependencies']}
    assert table_ref in dependencies[function_ref], \
        'a grant written as Ref:OrdersTable should resolve to that table'


def test_unresolved_grants_stay_on_the_document(tmp_path):
    _, out = _scan_cyclonedx(tmp_path, FIXTURES / 'terraform')
    document = json.loads(out.read_text())

    unresolved = [json.loads(v) for v in _properties(document, 'trustsource:obom:unresolved')]
    assert any(item['reason'] == 'aws-managed-policy' for item in unresolved)


def test_cyclonedx_refuses_more_than_one_source(tmp_path):
    result, _ = _scan_cyclonedx(tmp_path, FIXTURES / 'cloudformation', FIXTURES / 'terraform')
    assert result.exit_code == 2
    assert 'one at a time' in result.output


def test_ts_format_still_carries_the_graph(tmp_path):
    """The native format keeps its own shape; the CycloneDX output is additive."""
    runner = CliRunner()
    out = tmp_path / 'obom.json'
    result = runner.invoke(
        cli, ['--config', str(tmp_path / 'config'), 'scan', '-o', str(out),
              str(FIXTURES / 'cloudformation')], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    document = json.loads(out.read_text())[0]
    assert set(document) >= {'module', 'source', 'tool', 'resources', 'edges', 'unresolved'}
    assert document['tool']['version'] == ts_obom.__version__
