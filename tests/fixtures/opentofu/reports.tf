# Legacy Terraform version of reports.tofu. OpenTofu ignores this file
# because a .tofu file with the same base name exists next to it.

resource "aws_iam_role" "reports" {
  name               = "orderdesk-reports"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [] })
}

resource "aws_iam_role_policy" "reports_legacy" {
  name = "orderdesk-reports-legacy"
  role = aws_iam_role.reports.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:DeleteBucket"]
      Resource = "arn:aws:s3:::orderdesk-reports"
    }]
  })
}
