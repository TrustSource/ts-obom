"""Deployment naming and the parameter source that gives it meaning."""
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

import ts_obom.cli.scan  # noqa: F401  registers the scan command, as start() does
from ts_obom.cli import cli

FIXTURES = Path(__file__).parent / 'fixtures'

TFVARS_MAIN = '''
variable "bucket" {
  type    = string
  default = "orderdesk-dev-reports"
}
resource "aws_iam_role" "reports" {
  name               = "reports"
  assume_role_policy = "{}"
}
resource "aws_iam_role_policy" "reports_read" {
  role   = aws_iam_role.reports.id
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow",
      Action   = ["s3:GetObject"],
      Resource = "arn:aws:s3:::${var.bucket}/*"
    }]
  })
}
'''


@pytest.fixture
def tf_sources(tmp_path):
    """Terraform sources whose bucket name comes from a variable, plus a
    .tfvars file holding another environment's value for it."""
    sources = tmp_path / 'infra'
    sources.mkdir()
    (sources / 'main.tf').write_text(TFVARS_MAIN)
    (sources / 'params4PRD.tfvars').write_text('bucket = "orderdesk-prod-reports"\n')
    return sources


def _scan(tmp_path, *args, fmt='ts'):
    runner = CliRunner()
    return runner.invoke(
        cli, ['--config', str(tmp_path / 'config'), 'scan', '-f', fmt, *args],
        catch_exceptions=False)


def _document(result, fmt='ts'):
    """The scan prints progress lines first; the document starts on the line
    that holds nothing but its opening bracket."""
    match = re.search(r'(?m)^[\[{]$', result.output)
    assert match, result.output
    document = json.loads(result.output[match.start():])
    return document[0] if fmt == 'ts' else document


def test_var_file_changes_what_the_scan_sees(tmp_path, tf_sources):
    """The point of the whole exercise: a named deployment is only meaningful
    if its parameter values actually reach the graph."""
    without = _document(_scan(tmp_path, '--cloudformation:ignore', str(tf_sources)))
    with_vars = _document(_scan(tmp_path, '--cloudformation:ignore',
                                '--terraform:var-file', str(tf_sources / 'params4PRD.tfvars'),
                                str(tf_sources)))

    assert without['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-dev-reports/*'
    assert with_vars['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-prod-reports/*'


def test_parameter_source_names_the_file_per_frontend(tmp_path, tf_sources):
    document = _document(_scan(tmp_path, '--cloudformation:ignore',
                               '--terraform:var-file', str(tf_sources / 'params4PRD.tfvars'),
                               str(tf_sources)))
    assert document['parameterSource'] == 'terraform=params4PRD.tfvars'


def test_a_half_parameterised_scan_says_so(tmp_path, tf_sources):
    """CloudFormation cannot take parameters yet. A scan with both front-ends
    active must not look fully parameterised because Terraform was."""
    document = _document(_scan(tmp_path, '--terraform:var-file',
                               str(tf_sources / 'params4PRD.tfvars'), str(tf_sources)))
    assert document['parameterSource'] == 'cloudformation=defaults,terraform=params4PRD.tfvars'


def test_without_any_parameter_source_it_is_defaults(tmp_path):
    document = _document(_scan(tmp_path, str(FIXTURES / 'cloudformation')))
    assert document['parameterSource'] == 'defaults'


def test_naming_a_deployment_without_parameters_warns(tmp_path):
    """Two deployments scanned this way produce identical documents. Saying so
    once is cheaper than the wrong conclusion drawn from it later."""
    result = _scan(tmp_path, '--deployment', 'PRD', str(FIXTURES / 'cloudformation'))

    assert result.exit_code == 0
    assert 'PRD' in result.output and 'defaults' in result.output


def test_deployment_and_parameter_source_reach_the_cyclonedx_document(tmp_path, tf_sources):
    result = _scan(tmp_path, '--cloudformation:ignore', '--deployment', 'PRD',
                   '--terraform:var-file', str(tf_sources / 'params4PRD.tfvars'),
                   str(tf_sources), fmt='cyclonedx')
    document = _document(result, fmt='cyclonedx')

    properties = {p['name']: p['value'] for p in document['metadata']['properties']}
    assert properties['trustsource:obom:deployment'] == 'PRD'
    assert properties['trustsource:obom:parameterSource'] == 'terraform=params4PRD.tfvars'


def test_parameter_source_is_always_present(tmp_path):
    """Absence would be ambiguous -- a reader could not tell an unparameterised
    scan from an older document that never recorded it."""
    result = _scan(tmp_path, str(FIXTURES / 'cloudformation'), fmt='cyclonedx')
    properties = {p['name']: p['value']
                  for p in _document(result, fmt='cyclonedx')['metadata']['properties']}

    assert properties['trustsource:obom:parameterSource'] == 'defaults'
    assert 'trustsource:obom:deployment' not in properties


def test_document_declares_the_operations_lifecycle(tmp_path):
    """CycloneDX's own way of saying this is an Operations BOM, next to the
    TrustSource marker a platform consumer looks for."""
    result = _scan(tmp_path, str(FIXTURES / 'cloudformation'), fmt='cyclonedx')
    assert _document(result, fmt='cyclonedx')['metadata']['lifecycles'] == [
        {'phase': 'operations'}]
