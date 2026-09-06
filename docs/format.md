# Result format

The default format (`-f ts`) is a JSON array with one document per scanned directory.

```json
[
  {
    "module": "backend",
    "moduleId": "obom:backend",
    "source": "/work/orderdesk/backend",
    "tag": "v2.4.17",
    "branch": "main",
    "tool": {
      "name": "ts-obom",
      "version": "0.1.0",
      "frontends": ["cloudformation", "terraform"],
      "generatedAt": "2026-09-06T12:00:00+00:00"
    },
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

## Header

The header mirrors the header of a ts-scan dependency scan so that both results can be correlated per module.

| Field | Meaning |
|-------|---------|
| `module` | Name of the scanned directory |
| `moduleId` | `obom:<module>` |
| `source` | Absolute path that was scanned |
| `tag`, `branch` | Values of `--tag` / `--branch`, omitted when not given |
| `tool.name`, `tool.version` | Producer |
| `tool.frontends` | Front-ends that were active for this scan |
| `tool.generatedAt` | UTC timestamp |

## Edges

Each edge is one grant. Several statements for the same principal produce several edges; the scanner does not merge or minimise them, so that every edge can be traced back to exactly one declaration.

| Field | Meaning |
|-------|---------|
| `principal` | The identity that holds the grant. CloudFormation: resource type and logical id (`AWS::IAM::Role.ReportRole`, `AWS::Serverless::Function.OrderApiFunction`). Terraform: the compute resource that assumes the role (`aws_lambda_function.worker`) when it can be resolved, otherwise the role, user or group itself |
| `resource` | The resource the grant applies to, as written: an ARN, a `!Ref` target rendered as `Ref:<logical id>`, `*` |
| `actions` | IAM actions, expanded for the SAM policy templates the scanner knows |
| `effect` | `Allow` or `Deny`, as declared |
| `grantedVia` | Where the grant comes from: `AWS::IAM::Role inline policy '<name>'`, `SAM policy template '<name>'`, `SAM inline Policies[].Statement` or the Terraform resource address |

## Unresolved

Grants the scanner recognised but could not expand without external knowledge.

| Field | Meaning |
|-------|---------|
| `principal` | The identity concerned |
| `reason` | Short category, for example a managed policy attachment or a SAM policy template the scanner does not know yet |
| `detail` | The reference that could not be expanded |

Unresolved entries are not errors. They mark the places where a reviewer has to look up the policy by hand, and they are the backlog for extending the scanner.

## Graphviz (`-f dot`)

`-f dot` renders the same content as a directed graph: principals and resources as nodes, one edge per grant labelled with its actions, `Deny` edges dashed and red, unresolved principals dotted. Each scanned directory becomes a cluster.

## A note on the name

CycloneDX uses the abbreviation OBOM for an *Operations* Bill of Materials that describes runtime configuration. The TrustSource OBOM is an *Ownership* Bill of Materials and describes access rights. The two do not overlap in content; when exchanging documents with CycloneDX tooling, say which one you mean.
