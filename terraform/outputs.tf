output "api_endpoint" {
  description = "API Gateway endpoint URL for the /analyze route"
  value       = "${aws_apigatewayv2_api.oneclick_api.api_endpoint}/analyze"
}

output "intake_lambda_name" {
  description = "Name of the intake Lambda function"
  value       = aws_lambda_function.intake.function_name
}

output "vlocity_table" {
  description = "DynamoDB table for Vlocity Error Logs"
  value       = aws_dynamodb_table.vlocity_error_logs.name
}

output "exception_table" {
  description = "DynamoDB table for PS Exception Logs"
  value       = aws_dynamodb_table.ps_exception_logs.name
}
