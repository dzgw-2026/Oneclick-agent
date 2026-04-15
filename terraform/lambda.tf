# --- IAM Role for the Intake Lambda ---

resource "aws_iam_role" "intake_lambda_role" {
  name = "${var.project_name}-intake-lambda-role"

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

resource "aws_iam_role_policy" "intake_lambda_policy" {
  name = "${var.project_name}-intake-lambda-policy"
  role = aws_iam_role.intake_lambda_role.id

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
          "bedrock-agentcore:InvokeAgentRuntime"
        ]
        Resource = "*"
      }
    ]
  })
}

# --- Intake Lambda (validates request, forwards to AgentCore Runtime) ---

data "archive_file" "intake" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/handler.py"
  output_path = "${path.module}/build/intake.zip"
}

resource "aws_lambda_function" "intake" {
  filename         = data.archive_file.intake.output_path
  function_name    = "${var.project_name}-intake"
  role             = aws_iam_role.intake_lambda_role.arn
  handler          = "handler.handler"
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = 128
  source_code_hash = data.archive_file.intake.output_base64sha256

  environment {
    variables = {
      AGENT_RUNTIME_ID    = var.agent_runtime_id
      AGENT_NAME          = "OneClickAgent"
      AWS_REGION_OVERRIDE = var.aws_region
    }
  }
}

# --- Lambda Function URL (bypasses API Gateway 30s timeout) ---

resource "aws_lambda_function_url" "intake" {
  function_name      = aws_lambda_function.intake.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "function_url_public" {
  statement_id           = "AllowPublicFunctionURL"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.intake.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
