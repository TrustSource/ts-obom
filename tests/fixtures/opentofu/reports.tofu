# Takes precedence over reports.tf (OpenTofu 1.8+ file precedence rule).

resource "aws_iam_role" "reports" {
  name               = "orderdesk-reports"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [] })
}

resource "aws_iam_role_policy" "reports_read" {
  name = "orderdesk-reports-read"
  role = aws_iam_role.reports.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "arn:aws:s3:::orderdesk-reports/*"
    }]
  })
}
