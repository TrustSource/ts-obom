provider "aws" {
  region = "eu-central-1"
}

resource "aws_iam_role" "worker" {
  name = "orderdesk-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "worker_exports" {
  name = "orderdesk-worker-exports"
  role = aws_iam_role.worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject"]
      Resource = "arn:aws:s3:::orderdesk-exports/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "worker_readonly" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSQSReadOnlyAccess"
}

resource "aws_lambda_function" "worker" {
  function_name = "orderdesk-worker"
  role          = aws_iam_role.worker.arn
  handler       = "worker.handler"
  runtime       = "python3.12"
  filename      = "worker.zip"
}
