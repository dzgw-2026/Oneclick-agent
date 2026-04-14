variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "oneclick-agent"
}

variable "bedrock_model_id" {
  description = "Bedrock foundation model ID for the agent"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "lambda_runtime" {
  description = "Python runtime version for Lambda functions"
  type        = string
  default     = "python3.12"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds (must accommodate multi-turn Converse API loop)"
  type        = number
  default     = 120
}

variable "vlocity_table_name" {
  description = "DynamoDB table name for mock Vlocity Error Logs"
  type        = string
  default     = "VlocityErrorLogs"
}

variable "exception_table_name" {
  description = "DynamoDB table name for mock PS Exception Logs"
  type        = string
  default     = "PSExceptionLogs"
}
