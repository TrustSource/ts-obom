# ts-obom Roadmap

The backlog below is kept in rough priority order and mirrors the one in [architecture.md](architecture.md), where each item carries its technical context. We are a small team, so priorities are negotiable — if you need something sooner, reach out or take it into your hands. See [Adding Features](adding.md).

## Next

**1. Principal resolution for ECS and Batch (Terraform).** Role-to-principal resolution currently follows the `role`, `user` and `group` attributes. `aws_ecs_task_definition` references its role through `task_role_arn` / `execution_role_arn` and `aws_batch_job_definition` through `job_role_arn`, so their grants are attributed to the IAM role instead of the task or job definition.

**2. CIS benchmarks as an optional extra.** A `ts-obom[checks]` install would depend on the real `checkov` package and run a benchmark subset over the sources already scanned, with the findings carried in the OBOM itself. Everything on the ts-obom side is in place; what decides whether it is worth doing is the platform work that makes such findings usable. See ADR-008.

**3. `AWS::IAM::Policy` / `AWS::IAM::ManagedPolicy`** resources, and Terraform `aws_iam_policy` documents referenced by an attachment. Today these end up in `unresolved`.

**4. Resource based policies** — bucket, queue and topic policies. A grant can also be written on the resource rather than on the identity, and that half is not read yet.

**5. A Kubernetes RBAC front-end.** Roles, bindings and service accounts are the same question in a different language.

## Not planned

**Evaluating what the OBOM says.** ts-obom produces evidence; judging it — policies, benchmarks, risk — is the platform's job, and duplicating that here would give two answers to the same question. See ADR-008.

**Resolving anything that needs credentials.** Managed policy ARNs, live account state, deployed drift. A scan reads declared infrastructure and runs offline; what it cannot resolve it reports as unresolved. Live inventory is a different tool with a different trust model.
