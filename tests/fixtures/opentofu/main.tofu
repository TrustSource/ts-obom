terraform {
  required_version = ">= 1.8.0"

  encryption {
    key_provider "pbkdf2" "local" {
      passphrase = var.state_passphrase
    }
    method "aes_gcm" "default" {
      keys = key_provider.pbkdf2.local
    }
    state {
      method = method.aes_gcm.default
    }
  }
}

variable "state_passphrase" {
  type      = string
  sensitive = true
  default   = "fixture-only-passphrase-32-chars!!"
}

provider "aws" {
  region = "eu-central-1"
}

resource "aws_iam_role" "importer" {
  name = "orderdesk-importer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "importer_queue" {
  name = "orderdesk-importer-queue"
  role = aws_iam_role.importer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage"]
      Resource = "arn:aws:sqs:eu-central-1:123456789012:orderdesk-imports"
    }]
  })
}

resource "aws_ecs_task_definition" "importer" {
  family                = "orderdesk-importer"
  task_role_arn         = aws_iam_role.importer.arn
  container_definitions = jsonencode([{ name = "importer", image = "orderdesk/importer:2.4" }])
}
