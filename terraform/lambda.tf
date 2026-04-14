# --- IAM Role for the Agent Lambda ---

resource "aws_iam_role" "agent_lambda_role" {
  name = "${var.project_name}-agent-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "agent_lambda_policy" {
  name = "${var.project_name}-agent-lambda-policy"
  role = aws_iam_role.agent_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.vlocity_error_logs.arn,
          "${aws_dynamodb_table.vlocity_error_logs.arn}/index/*",
          aws_dynamodb_table.ps_exception_logs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      }
    ]
  })
}

# --- Agent Lambda (single function — tools execute in-process) ---

data "archive_file" "agent" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas"
  output_path = "${path.module}/build/agent.zip"
}

resource "aws_lambda_function" "agent" {
  filename         = data.archive_file.agent.output_path
  function_name    = "${var.project_name}-agent"
  role             = aws_iam_role.agent_lambda_role.arn
  handler          = "handler.handler"
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = 256
  source_code_hash = data.archive_file.agent.output_base64sha256

  environment {
    variables = {
      BEDROCK_MODEL_ID    = var.bedrock_model_id
      VLOCITY_TABLE       = var.vlocity_table_name
      EXCEPTION_TABLE     = var.exception_table_name
      AWS_REGION_OVERRIDE = var.aws_region
    }
  }
}
