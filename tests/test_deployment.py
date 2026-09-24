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


CFN_TEMPLATE = """
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  BucketName:
    Type: String
    Default: orderdesk-dev-reports
Resources:
  ReportRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal: {Service: lambda.amazonaws.com}
            Action: sts:AssumeRole
      Policies:
        - PolicyName: read-reports
          PolicyDocument:
            Statement:
              - Effect: Allow
                Action: s3:GetObject
                Resource: !Sub 'arn:aws:s3:::${BucketName}/*'
"""


@pytest.fixture
def cfn_sources(tmp_path):
    """A template whose bucket name comes from a parameter, plus one parameter
    file per deployment -- the pattern the TrustSource repositories deploy with:
    one template, one parameter file per environment."""
    sources = tmp_path / 'cfn-infra'
    sources.mkdir()
    (sources / 'template.yaml').write_text(CFN_TEMPLATE)
    (sources / 'params4PRD.json').write_text(json.dumps([
        {'ParameterKey': 'BucketName', 'ParameterValue': 'orderdesk-prod-reports'},
    ]))
    (sources / 'flat.json').write_text(json.dumps({'BucketName': 'orderdesk-flat'}))
    return sources


@pytest.fixture
def tf_sources(tmp_path):
    """Terraform sources whose bucket name comes from a variable, plus a
    .tfvars file holding another environment's value for it."""
    sources = tmp_path / 'tf-infra'
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


def test_cloudformation_parameters_replace_the_template_defaults(tmp_path, cfn_sources):
    """The pattern this exists for: same template, one parameter file per
    environment. Without the file the scan reports the template's default,
    which is neither deployment's value."""
    without = _document(_scan(tmp_path, '--terraform:ignore', str(cfn_sources)))
    with_params = _document(_scan(tmp_path, '--terraform:ignore',
                                  '--cloudformation:parameters',
                                  str(cfn_sources / 'params4PRD.json'), str(cfn_sources)))

    assert without['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-dev-reports/*'
    assert with_params['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-prod-reports/*'
    assert with_params['parameterSource'] == 'cloudformation=params4PRD.json'


def test_a_flat_parameter_mapping_is_accepted_too(tmp_path, cfn_sources):
    document = _document(_scan(tmp_path, '--terraform:ignore',
                               '--cloudformation:parameters', str(cfn_sources / 'flat.json'),
                               str(cfn_sources)))
    assert document['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-flat/*'


def test_a_value_for_an_undeclared_parameter_is_reported(tmp_path, cfn_sources):
    """Usually a typo or the wrong file. Silently ignoring it would let
    parameterSource claim more than the scan actually applied."""
    params = cfn_sources / 'typo.json'
    params.write_text(json.dumps([
        {'ParameterKey': 'BucketName', 'ParameterValue': 'orderdesk-prod-reports'},
        {'ParameterKey': 'BuckettName', 'ParameterValue': 'typo'},
    ]))

    document = _document(_scan(tmp_path, '--terraform:ignore',
                               '--cloudformation:parameters', str(params), str(cfn_sources)))

    unused = [u for u in document['unresolved'] if u['reason'] == 'unused-parameter']
    assert len(unused) == 1 and 'BuckettName' in unused[0]['detail']
    # The one that does exist was still applied.
    assert document['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-prod-reports/*'


def test_parameters_not_named_in_the_file_keep_their_default(tmp_path, cfn_sources):
    """As on a real deployment: --parameter-overrides only overrides what it
    names."""
    params = cfn_sources / 'empty.json'
    params.write_text(json.dumps([]))

    document = _document(_scan(tmp_path, '--terraform:ignore',
                               '--cloudformation:parameters', str(params), str(cfn_sources)))
    assert document['edges'][0]['resource'] == 'arn:aws:s3:::orderdesk-dev-reports/*'


def test_both_front_ends_parameterised_is_a_full_source(tmp_path, cfn_sources, tf_sources):
    document = _document(_scan(tmp_path,
                               '--cloudformation:parameters',
                               str(cfn_sources / 'params4PRD.json'),
                               '--terraform:var-file', str(tf_sources / 'params4PRD.tfvars'),
                               str(cfn_sources)))
    assert document['parameterSource'] == (
        'cloudformation=params4PRD.json,terraform=params4PRD.tfvars')


def test_naming_a_deployment_with_parameters_does_not_warn(tmp_path, cfn_sources):
    result = _scan(tmp_path, '--terraform:ignore', '--deployment', 'PRD',
                   '--cloudformation:parameters', str(cfn_sources / 'params4PRD.json'),
                   str(cfn_sources))
    assert result.exit_code == 0
    assert 'no parameter values were supplied' not in result.output
