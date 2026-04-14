# --- S3 ---
#
# The S3 bucket previously used for OpenAPI schemas is no longer needed.
# Tool definitions are now embedded in the Lambda code (tools/definitions.py)
# and passed inline to the Bedrock Converse API.

# Data source for account ID (used by other modules)
data "aws_caller_identity" "current" {}

