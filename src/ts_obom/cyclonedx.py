# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""
Renders a scan result as a CycloneDX Operations BOM, in the shape TrustSource's
OBOM API accepts.

The BOM skeleton is built by Checkov's own CycloneDX exporter -- the vendored
``checkov.common.output.cyclonedx.CycloneDX`` -- rather than by hand, so the
component identity (the ``pkg:<front-end>/<repo>/<file>/<resource>@sha1:<file
hash>`` purl and the SHA-1 of the declaring file) is byte-for-byte what
``checkov -o cyclonedx_json`` produces for the same sources. Checkov drives that
exporter from a ``Report``; only five attributes of one are ever read, so a
scan's resources are handed over as a tiny stand-in (``_InventoryReport``)
instead of dragging in checkov's whole reporting subsystem.

What Checkov cannot know is then added here:

* ``metadata.properties`` carries ``trustsource:bomType = obom``. Without that
  marker ts-obom-ingest rejects the document with 400 -- it is what makes a
  CycloneDX document an OBOM rather than an SBOM.
* ``metadata.component`` is the scanned module, so the document says what it
  describes.
* ts-obom is added to ``metadata.tools`` next to checkov, and checkov's entry
  gets the vendored copy's version (the exporter reads it from installed package
  metadata, and there is no installed checkov here).
* Component types beyond checkov's blanket ``application``: a Lambda function is
  a ``platform``, a bucket or a table is ``data``, a task definition is a
  ``container``. Unmapped resource types keep checkov's ``application``.
* The access grants (``edges``) become component properties and, where the
  grant's target resolves to another component, ``dependencies`` entries -- so
  the document is a graph of what runs on what and may touch what, not a flat
  list.
"""

from __future__ import annotations

import json
import typing as t

from . import obom

if t.TYPE_CHECKING:
    from . import ObomScan


#: Namespace for every property this module writes, so a consumer can tell
#: ts-obom's additions from CycloneDX's own fields and from checkov's.
PROPERTY_PREFIX = 'trustsource:obom'

#: The marker ts-obom-ingest looks for. Defined by the platform, not by us.
BOM_TYPE_PROPERTY = 'trustsource:bomType'
BOM_TYPE_VALUE = 'obom'


def _component_types() -> t.Dict[str, t.Any]:
    """Resource type -> CycloneDX component type.

    Deliberately partial, in the same spirit as the SAM policy template table:
    an unmapped resource type falls back to checkov's ``application`` rather
    than being guessed at. Extend as real templates turn up types worth
    distinguishing.
    """
    from cyclonedx.model.component import ComponentType

    compute = [
        'AWS::Serverless::Function', 'AWS::Lambda::Function', 'AWS::EC2::Instance',
        'AWS::ECS::Service', 'AWS::Batch::JobDefinition', 'AWS::Serverless::Api',
        'AWS::ApiGateway::RestApi',
        'aws_lambda_function', 'aws_instance', 'aws_ecs_service',
        'aws_batch_job_definition', 'aws_apigatewayv2_api', 'aws_api_gateway_rest_api',
    ]
    container = [
        'AWS::ECS::TaskDefinition', 'AWS::ECR::Repository',
        'aws_ecs_task_definition', 'aws_ecr_repository',
    ]
    data = [
        'AWS::S3::Bucket', 'AWS::DynamoDB::Table', 'AWS::SQS::Queue', 'AWS::SNS::Topic',
        'AWS::RDS::DBInstance', 'AWS::RDS::DBCluster', 'AWS::SecretsManager::Secret',
        'AWS::KMS::Key', 'AWS::EFS::FileSystem',
        'aws_s3_bucket', 'aws_dynamodb_table', 'aws_sqs_queue', 'aws_sns_topic',
        'aws_db_instance', 'aws_rds_cluster', 'aws_secretsmanager_secret',
        'aws_kms_key', 'aws_efs_file_system',
    ]

    mapping: t.Dict[str, t.Any] = {}
    for name in compute:
        mapping[name] = ComponentType.PLATFORM
    for name in container:
        mapping[name] = ComponentType.CONTAINER
    for name in data:
        mapping[name] = ComponentType.DATA
    return mapping


class _InventoryReport:
    """Stand-in for ``checkov.common.output.report.Report``.

    The CycloneDX exporter reads exactly ``check_type``, ``passed_checks``,
    ``skipped_checks``, ``failed_checks`` and ``extra_resources`` off a report.
    ts-obom runs no checks, so the first four are empty and every resource is an
    ``extra_resource`` -- checkov's own term for a resource that appears in the
    BOM without a finding attached to it.
    """

    def __init__(self, check_type: str, extra_resources: t.List[t.Any]):
        self.check_type = check_type
        self.extra_resources = extra_resources
        self.passed_checks: t.List[t.Any] = []
        self.skipped_checks: t.List[t.Any] = []
        self.failed_checks: t.List[t.Any] = []


def _reports_from(result: obom.ObomResult) -> t.List[_InventoryReport]:
    """One report per front-end. The front-end name becomes the purl type
    (``pkg:cloudformation/...``, ``pkg:terraform/...``), which is how checkov
    spells it too."""
    obom.require_checkov()
    from checkov.common.output.extra_resource import ExtraResource

    by_frontend: t.Dict[str, t.List[t.Any]] = {}
    for resource in result.resources:
        by_frontend.setdefault(resource.frontend, []).append(
            ExtraResource(
                file_abs_path=resource.fileAbsPath,
                file_path=resource.filePath,
                resource=resource.id,
            )
        )
    return [_InventoryReport(frontend, resources)
            for frontend, resources in by_frontend.items()]


# cyclonedx-python-lib builds its model classes with py-serializable's
# `@serializable_class` decorator, which pyright cannot see through: every
# constructor call below is reported as "No parameter named ...". The calls are
# correct -- the library's own signatures are keyword-only -- so the reports are
# suppressed at the call site rather than by loosening the type checker.
def _property(name: str, value: str) -> t.Any:
    from cyclonedx.model import Property
    return Property(name=name, value=value)  # pyright: ignore[reportCallIssue]


def _set_metadata(bom: t.Any, scan: 'ObomScan') -> None:
    from cyclonedx.model.component import Component, ComponentType
    from cyclonedx.model import Tool

    from . import __version__

    bom.metadata.component = Component(
        name=scan.module, type=ComponentType.APPLICATION,  # pyright: ignore[reportCallIssue]
        bom_ref=scan.moduleId, version=scan.tag or None)  # pyright: ignore[reportCallIssue]

    bom.metadata.properties.add(_property(BOM_TYPE_PROPERTY, BOM_TYPE_VALUE))
    bom.metadata.properties.add(_property(f'{PROPERTY_PREFIX}:source', str(scan.source)))
    bom.metadata.properties.add(
        _property(f'{PROPERTY_PREFIX}:frontends', ','.join(scan.frontends)))
    if scan.tag:
        bom.metadata.properties.add(_property(f'{PROPERTY_PREFIX}:tag', scan.tag))
    if scan.branch:
        bom.metadata.properties.add(_property(f'{PROPERTY_PREFIX}:branch', scan.branch))
    if scan.deployment:
        bom.metadata.properties.add(
            _property(f'{PROPERTY_PREFIX}:deployment', scan.deployment))
    # Always written, never omitted: a reader comparing two documents has to be
    # able to tell "scanned with this deployment's parameters" from "scanned
    # with whatever the templates default to". Absence would be ambiguous.
    bom.metadata.properties.add(
        _property(f'{PROPERTY_PREFIX}:parameterSource', scan.parameterSource))

    bom.metadata.tools.add(
        Tool(vendor='EACG', name='ts-obom', version=__version__))  # pyright: ignore[reportCallIssue]

    # The exporter reads checkov's version from installed package metadata and
    # falls back to "UNKNOWN" -- there is no checkov install here, the graph
    # builder and this exporter are vendored. Say which copy actually ran.
    from checkov.version import version as vendored_checkov_version
    for tool in bom.metadata.tools:
        if tool.name == 'checkov' and tool.version in (None, '', 'UNKNOWN'):
            tool.version = f'{vendored_checkov_version}+ts-obom.vendored'


def _index_components(bom: t.Any) -> t.Dict[str, t.Any]:
    """Component by resource id. ``Component.name`` is the graph vertex id the
    edges refer to, which is what makes the join below possible."""
    return {component.name: component for component in bom.components}


def _resolve_grant_target(target: str, components: t.Dict[str, t.Any]) -> t.Optional[t.Any]:
    """Best effort: turn an edge's ``resource`` label back into a component.

    A grant is written against whatever the template said -- a literal ARN, a
    ``Ref:OrdersTable``, a ``GetAtt:Table.Arn``, ``*``. Only the reference forms
    can point at something else in the same sources, and only by logical id, so
    that is all this resolves. An ARN naming a resource outside the template has
    no component to point at, and saying so by leaving the dependency out is
    more honest than inventing one.
    """
    for prefix in ('Ref:', 'GetAtt:', 'Sub:'):
        if not target.startswith(prefix):
            continue
        logical_id = target[len(prefix):].split('.')[0]
        if logical_id in components:
            return components[logical_id]
        for name, component in components.items():
            if name.endswith(f'.{logical_id}'):
                return component
        return None
    return components.get(target)


def _apply_grants(bom: t.Any, result: obom.ObomResult) -> None:
    components = _index_components(bom)
    dependencies: t.Dict[t.Any, t.List[t.Any]] = {}

    for edge in result.edges:
        principal = components.get(edge.principal)
        grant = {
            'resource': edge.resource,
            'actions': edge.actions,
            'effect': edge.effect,
            'grantedVia': edge.grantedVia,
        }
        if principal is None:
            # A grant whose principal is not a declared resource (an IAM role
            # referenced only by name, say). Keep it on the document rather than
            # dropping it, next to the unresolved entries.
            grant['principal'] = edge.principal
            bom.metadata.properties.add(
                _property(f'{PROPERTY_PREFIX}:grant', json.dumps(grant, sort_keys=True)))
            continue

        principal.properties.add(
            _property(f'{PROPERTY_PREFIX}:grant', json.dumps(grant, sort_keys=True)))

        target = _resolve_grant_target(edge.resource, components)
        if target is not None and target is not principal:
            targets = dependencies.setdefault(principal, [])
            if target not in targets:
                targets.append(target)

    for principal, targets in dependencies.items():
        bom.register_dependency(principal, targets)

    for item in result.unresolved:
        bom.metadata.properties.add(_property(
            f'{PROPERTY_PREFIX}:unresolved',
            json.dumps({'principal': item.principal, 'reason': item.reason,
                        'detail': item.detail}, sort_keys=True)))


def _apply_component_types(bom: t.Any, result: obom.ObomResult) -> None:
    types = _component_types()
    by_id = {resource.id: resource for resource in result.resources}

    for component in bom.components:
        resource = by_id.get(component.name)
        if resource is None:
            continue
        component.properties.add(
            _property(f'{PROPERTY_PREFIX}:resourceType', resource.resourceType))
        component.properties.add(
            _property(f'{PROPERTY_PREFIX}:frontend', resource.frontend))
        component_type = types.get(resource.resourceType)
        if component_type is not None:
            component.type = component_type


def build_bom(scan: 'ObomScan') -> t.Any:
    """Builds the CycloneDX BOM for one scanned directory."""
    obom.require_checkov()
    from checkov.common.output.cyclonedx import CycloneDX

    reports = _reports_from(scan.result)
    # repo_id is checkov's purl namespace prefix; the module name keeps the
    # components of two modules apart in a document that is later read together.
    exporter = CycloneDX(reports=t.cast(t.Any, reports), repo_id=scan.module)
    # Typed loosely for the same reason as the constructor calls above: the
    # library's decorated model classes defeat pyright's inference.
    bom: t.Any = exporter.bom

    _set_metadata(bom, scan)
    _apply_component_types(bom, scan.result)
    _apply_grants(bom, scan.result)

    # The module is what the document describes, and it is deployed as all of
    # these resources -- without that edge the dependency graph has no root and
    # a CycloneDX consumer cannot tell where to start reading.
    if bom.metadata.component is not None:
        bom.register_dependency(bom.metadata.component, list(bom.components))
    return bom


#: What CycloneDX itself calls an Operations BOM. `trustsource:bomType` is the
#: marker the platform requires; this is the standard-native way to say the same
#: thing, and a CycloneDX consumer that knows nothing about TrustSource can read
#: it. Declared as data because the pinned library cannot model it -- see below.
OPERATIONS_LIFECYCLE = [{'phase': 'operations'}]


def to_json(scan: 'ObomScan') -> str:
    """The BOM as a CycloneDX JSON string.

    ``metadata.lifecycles`` is inserted after serialisation rather than set on
    the model: it exists in the CycloneDX schema from 1.5 on, but not in
    cyclonedx-python-lib 7.x, and that major version is fixed by the vendored
    checkov exporter (checkov pins the library below 8.0). Writing the two
    fields we need into the emitted document is contained and reversible; moving
    the pin to get one metadata field is not.
    """
    obom.require_checkov()
    from checkov.common.output.cyclonedx_consts import DEFAULT_CYCLONE_SCHEMA_VERSION
    from cyclonedx.output import make_outputter
    from cyclonedx.schema import OutputFormat

    document = json.loads(make_outputter(
        bom=build_bom(scan),
        output_format=OutputFormat.JSON,
        schema_version=DEFAULT_CYCLONE_SCHEMA_VERSION,
    ).output_as_string())

    document.setdefault('metadata', {})['lifecycles'] = OPERATIONS_LIFECYCLE
    return json.dumps(document, indent=2)
