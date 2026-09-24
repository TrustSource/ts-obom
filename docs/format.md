# Result format

***ts-obom*** writes two formats. `-f cyclonedx` produces the **Operations BOM** the TrustSource platform stores; `-f ts` is the scanner's own, fuller result, useful for tooling that wants the access graph without reading it back out of CycloneDX properties.

## CycloneDX (`-f cyclonedx`)

A CycloneDX 1.6 document, one per scanned directory. This is the only format the TrustSource OBOM API accepts, and what [`ts-obom upload`](usage.md#upload) sends.

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "serialNumber": "urn:uuid:437f88e0-1042-487e-8b14-0c36d83564e5",
  "version": 1,
  "metadata": {
    "timestamp": "2026-09-22T08:00:00+00:00",
    "lifecycles": [{"phase": "operations"}],
    "component": {"bom-ref": "obom:backend", "name": "backend", "type": "application"},
    "properties": [
      {"name": "trustsource:bomType", "value": "obom"},
      {"name": "trustsource:obom:source", "value": "/work/orderdesk/backend"},
      {"name": "trustsource:obom:frontends", "value": "cloudformation,terraform"},
      {"name": "trustsource:obom:tag", "value": "v2.4.17"},
      {"name": "trustsource:obom:branch", "value": "main"},
      {"name": "trustsource:obom:deployment", "value": "PRD"},
      {"name": "trustsource:obom:parameterSource", "value": "terraform=params4PRD.tfvars"},
      {"name": "trustsource:obom:unresolved", "value": "{\"detail\": \"...\", \"principal\": \"aws_lambda_function.worker\", \"reason\": \"aws-managed-policy\"}"}
    ],
    "tools": [
      {"vendor": "EACG", "name": "ts-obom", "version": "0.3.0"},
      {"vendor": "bridgecrew", "name": "checkov", "version": "3.3.15+ts-obom.vendored"}
    ]
  },
  "components": [
    {
      "bom-ref": "pkg:cloudformation/backend/template.yaml/AWS::Serverless::Function.OrderApiFunction@sha1:6c94fa0b",
      "name": "AWS::Serverless::Function.OrderApiFunction",
      "type": "platform",
      "version": "sha1:6c94fa0b",
      "purl": "pkg:cloudformation/backend/template.yaml/AWS::Serverless::Function.OrderApiFunction@sha1:6c94fa0b",
      "properties": [
        {"name": "trustsource:obom:resourceType", "value": "AWS::Serverless::Function"},
        {"name": "trustsource:obom:frontend", "value": "cloudformation"},
        {"name": "trustsource:obom:grant", "value": "{\"actions\": [\"dynamodb:GetItem\"], \"effect\": \"Allow\", \"grantedVia\": \"SAM policy template 'DynamoDBCrudPolicy'\", \"resource\": \"Ref:OrdersTable\"}"}
      ]
    }
  ],
  "dependencies": [
    {"ref": "pkg:cloudformation/backend/template.yaml/AWS::Serverless::Function.OrderApiFunction@sha1:6c94fa0b",
     "dependsOn": ["pkg:cloudformation/backend/template.yaml/AWS::DynamoDB::Table.OrdersTable@sha1:6c94fa0b"]}
  ]
}
```

`metadata.lifecycles` declares `phase: operations` -- CycloneDX's own way of saying this is an Operations BOM, next to the TrustSource marker a platform consumer looks for.

### Components

One component per resource declared in the scanned sources -- not only the ones holding an IAM grant. A resource nobody was granted anything on is still part of how the module is operated.

| Field | Meaning |
|-------|---------|
| `name` | The resource as the graph names it: `<type>.<logical id>` for CloudFormation, `<type>.<name>` for Terraform |
| `type` | CycloneDX component type, mapped from the resource type (see below) |
| `version`, `purl`, `hashes` | Checkov's own component identity: the SHA-1 of the file declaring the resource. IaC resources carry no version of their own, so the hash of the declaring file is what identifies the state a component was read in. Identical to what `checkov -o cyclonedx_json` produces for the same sources |

The type mapping is deliberately partial, in the same spirit as the SAM policy template table:

| CycloneDX type | Resource types |
|----------------|----------------|
| `platform` | Compute: Lambda and SAM functions, EC2 instances, ECS services, Batch job definitions, API gateways |
| `container` | ECS task definitions, ECR repositories |
| `data` | Storage and state: S3 buckets, DynamoDB tables, SQS queues, SNS topics, RDS instances and clusters, Secrets Manager secrets, KMS keys, EFS file systems |
| `application` | Everything else, which is Checkov's own blanket type -- an unmapped resource type is not guessed at |

### Properties

Everything ts-obom adds is namespaced `trustsource:obom:*`, so it is distinguishable from CycloneDX's own fields and from Checkov's. The one exception is `trustsource:bomType`, which is the platform's marker and spelled the way the platform defines it -- without it, `ts-obom-ingest` rejects the document.

| Property | Where | Meaning |
|----------|-------|---------|
| `trustsource:bomType` | `metadata` | Always `obom`. What makes this an OBOM rather than an SBOM |
| `trustsource:obom:source` | `metadata` | The absolute path that was scanned |
| `trustsource:obom:frontends` | `metadata` | The front-ends active for this scan |
| `trustsource:obom:tag`, `:branch` | `metadata` | Values of `--tag` / `--branch`, omitted when not given |
| `trustsource:obom:deployment` | `metadata` | Which deployment this document describes -- an environment or a customer setup. Value of `--deployment`, omitted when not given |
| `trustsource:obom:parameterSource` | `metadata` | Where the parameter values came from. **Never omitted**: `defaults`, or `<front-end>=<file>` per active front-end. Two documents that both say `defaults` are not comparable, however they are named -- see [Usage](usage.md#deployments) |
| `trustsource:obom:unresolved` | `metadata` | One entry per grant the scanner recognised but could not expand, as JSON |
| `trustsource:obom:resourceType` | component | The IaC resource type, unmapped and as written |
| `trustsource:obom:frontend` | component | Which front-end found it |
| `trustsource:obom:grant` | component | One IAM grant held by this resource, as JSON: `{resource, actions[], effect, grantedVia}`. Repeated per grant. A grant whose principal is not itself a declared resource sits on `metadata` instead, with an extra `principal` field |

CycloneDX has no native model for an access grant, which is why they travel as properties. A consumer has to know the namespace; the trade-off is recorded in ADR-006.

### Dependencies

The module component depends on every resource -- that is what it is deployed as. A resource additionally depends on the resources its grants name, wherever the grant's target can be resolved back to another component in the same sources (`Ref:OrdersTable`, `GetAtt:OrdersTable.Arn`). A grant against a literal ARN outside the scanned sources produces no edge: there is nothing in the document to point at, and inventing a node would be worse than leaving the edge out.

## TrustSource native (`-f ts`)

A JSON array with one document per scanned directory. Not accepted by the API -- `ts-obom upload` rejects it and points at `-f cyclonedx` -- but it carries the access graph as data rather than as encoded properties.

```json
[
  {
    "module": "backend",
    "moduleId": "obom:backend",
    "source": "/work/orderdesk/backend",
    "tag": "v2.4.17",
    "branch": "main",
    "deployment": "PRD",
    "parameterSource": "terraform=params4PRD.tfvars",
    "tool": {
      "name": "ts-obom",
      "version": "0.3.0",
      "frontends": ["cloudformation", "terraform"],
      "generatedAt": "2026-09-22T12:00:00+00:00"
    },
    "resources": [
      {
        "id": "AWS::Serverless::Function.OrderApiFunction",
        "name": "AWS::Serverless::Function.OrderApiFunction",
        "resourceType": "AWS::Serverless::Function",
        "frontend": "cloudformation",
        "filePath": "template.yaml",
        "fileAbsPath": "/work/orderdesk/backend/template.yaml"
      }
    ],
    "edges": [
      {
        "principal": "AWS::Serverless::Function.OrderApiFunction",
        "resource": "Ref:OrdersTable",
        "actions": ["dynamodb:GetItem", "dynamodb:PutItem"],
        "effect": "Allow",
        "grantedVia": "SAM policy template 'DynamoDBCrudPolicy'"
      }
    ],
    "unresolved": [
      {
        "principal": "aws_lambda_function.worker",
        "reason": "aws-managed-policy",
        "detail": "actions live in AWS's own policy JSON, not the template: arn:aws:iam::aws:policy/AmazonSQSReadOnlyAccess"
      }
    ]
  }
]
```

### Header

The header mirrors the header of a ts-scan dependency scan so that both results can be correlated per module.

| Field | Meaning |
|-------|---------|
| `module` | Name of the scanned directory |
| `moduleId` | `obom:<module>`. A local label, **not** a TrustSource module identifier -- do not pass it to the API as `moduleIdentifier`; that would file the OBOM under a module of its own, next to the one the SBOM lands in. The upload names the scope explicitly with `--module-name` |
| `source` | Absolute path that was scanned |
| `tag`, `branch` | Values of `--tag` / `--branch`, omitted when not given |
| `deployment` | Value of `--deployment`, omitted when not given |
| `parameterSource` | Where the parameter values came from; never omitted. Same meaning as the CycloneDX property above |
| `tool.*` | Producer, the active front-ends and a UTC timestamp |

### Resources

The inventory: every resource block the graph builder found.

| Field | Meaning |
|-------|---------|
| `id` | The graph's own id for the resource; what an edge's `principal` refers to |
| `resourceType` | IaC resource type as written (`AWS::IAM::Role`, `aws_lambda_function`) |
| `frontend` | `cloudformation` or `terraform` |
| `filePath` | Declaring file, relative to the scanned directory |
| `fileAbsPath` | The same file, absolute |

### Edges

Each edge is one grant. Several statements for the same principal produce several edges; the scanner does not merge or minimise them, so that every edge can be traced back to exactly one declaration.

| Field | Meaning |
|-------|---------|
| `principal` | The identity that holds the grant. CloudFormation: resource type and logical id (`AWS::IAM::Role.ReportRole`). Terraform: the compute resource that assumes the role (`aws_lambda_function.worker`) when it can be resolved, otherwise the role, user or group itself |
| `resource` | The resource the grant applies to, as written: an ARN, a `!Ref` target rendered as `Ref:<logical id>`, `*` |
| `actions` | IAM actions, expanded for the SAM policy templates the scanner knows |
| `effect` | `Allow` or `Deny`, as declared |
| `grantedVia` | Where the grant comes from: `AWS::IAM::Role inline policy '<name>'`, `SAM policy template '<name>'`, `SAM inline Policies[].Statement` or the Terraform resource address |

### Unresolved

Grants the scanner recognised but could not expand without external knowledge.

| Field | Meaning |
|-------|---------|
| `principal` | The identity concerned |
| `reason` | Short category, for example a managed policy attachment, a SAM policy template the scanner does not know yet, or `unused-parameter` for a supplied parameter value no template declares |
| `detail` | The reference that could not be expanded |

Unresolved entries are not errors. They mark the places where a reviewer has to look up the policy by hand, and they are the backlog for extending the scanner.

## Graphviz (`-f dot`)

`-f dot` renders the access graph as a directed graph: principals and resources as nodes, one edge per grant labelled with its actions, `Deny` edges dashed and red, unresolved principals dotted. Each scanned directory becomes a cluster.

## A note on the name

OBOM here means **Operations Bill of Materials**, the same as in CycloneDX and the same as everywhere else on the TrustSource platform: a description of how something is operated -- what it runs on, what it is made of once deployed. Up to ts-obom 0.1.0 this documentation called it an *Ownership* Bill of Materials and described it as a different kind of document. That was wrong, and it is corrected in 0.2.0 (ADR-006). The IAM access graph is not gone -- it is what this scanner adds on top of the inventory.
