from pathlib import Path

from ts_obom import obom

FIXTURES = Path(__file__).parent / 'fixtures'


def _by_principal(result: obom.ObomResult):
    edges = {}
    for edge in result.edges:
        edges.setdefault(edge.principal, []).append(edge)
    return edges


def test_cloudformation_role_and_sam_function_grants():
    result = obom.extract_cloudformation(str(FIXTURES / 'cloudformation'))

    principals = _by_principal(result)
    assert principals, 'expected IAM grants from the CloudFormation fixture'

    all_actions = {action for edge in result.edges for action in edge.actions}
    assert 's3:GetObject' in all_actions
    assert 'dynamodb:PutItem' in all_actions, 'SAM DynamoDBCrudPolicy should expand to concrete actions'
    assert 'sqs:SendMessage' in all_actions

    effects = {edge.effect.casefold() for edge in result.edges}
    assert {'allow', 'deny'} <= effects

    assert set(principals) == {
        'AWS::IAM::Role.ReportRole',
        'AWS::Serverless::Function.OrderApiFunction',
    }
    granted_via = {edge.grantedVia for edge in result.edges}
    assert "AWS::IAM::Role inline policy 'read-report-bucket'" in granted_via
    assert "SAM policy template 'DynamoDBCrudPolicy'" in granted_via
    assert 'SAM inline Policies[].Statement' in granted_via

    sam_table = next(e for e in result.edges if 'dynamodb:PutItem' in e.actions)
    assert sam_table.resource == 'Ref:OrdersTable'
    assert result.unresolved == []


def test_terraform_inline_policy_and_attachment():
    result = obom.extract_terraform(str(FIXTURES / 'terraform'))

    all_actions = {action for edge in result.edges for action in edge.actions}
    assert {'s3:GetObject', 's3:PutObject'} <= all_actions

    resources = {edge.resource for edge in result.edges}
    assert 'arn:aws:s3:::orderdesk-exports/*' in resources

    # The role reference is resolved to the compute resource that assumes it.
    assert {edge.principal for edge in result.edges} == {'aws_lambda_function.worker'}
    assert result.edges[0].grantedVia == 'aws_iam_role_policy.worker_exports (Terraform inline policy)'

    # The managed policy attachment cannot be expanded without AWS access and
    # must show up as unresolved rather than being silently dropped.
    assert result.unresolved, 'managed policy attachment should be reported as unresolved'
    attachment = result.unresolved[0]
    assert attachment.principal == 'aws_lambda_function.worker'
    assert attachment.reason == 'aws-managed-policy'
    assert 'arn:aws:iam::aws:policy/AmazonSQSReadOnlyAccess' in attachment.detail


def test_extract_merges_both_frontends_and_tolerates_empty_directories(tmp_path):
    merged = obom.extract(str(FIXTURES / 'cloudformation'))
    assert merged.edges

    empty = obom.extract(str(tmp_path))
    assert empty.edges == []
    assert empty.unresolved == []


def test_result_to_dict_is_json_shaped():
    result = obom.extract_terraform(str(FIXTURES / 'terraform'))
    doc = result.to_dict()

    assert set(doc) == {'resources', 'edges', 'unresolved'}
    assert all(set(e) == {'principal', 'resource', 'actions', 'effect', 'grantedVia'} for e in doc['edges'])
    assert all(set(u) == {'principal', 'reason', 'detail'} for u in doc['unresolved'])


def test_opentofu_files_are_scanned_and_shadow_terraform_files():
    result = obom.extract_terraform(str(FIXTURES / 'opentofu'))

    actions = {action for edge in result.edges for action in edge.actions}
    # main.tofu (with an OpenTofu-only state encryption block) parses like Terraform
    assert {'sqs:ReceiveMessage', 'sqs:DeleteMessage'} <= actions
    # reports.tofu is used ...
    assert 's3:GetObject' in actions
    # ... and shadows reports.tf, whose grant must not appear
    assert 's3:DeleteBucket' not in actions

    granted_via = {edge.grantedVia for edge in result.edges}
    assert any('aws_iam_role_policy.importer_queue' in via for via in granted_via)
    assert any('aws_iam_role_policy.reports_read' in via for via in granted_via)
    assert not any('reports_legacy' in via for via in granted_via)
