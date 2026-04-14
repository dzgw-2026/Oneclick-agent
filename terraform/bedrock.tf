# --- Bedrock ---
#
# The agent now uses the Bedrock Converse API directly (bedrock:InvokeModel)
# from the Lambda function.  No pre-provisioned Bedrock Agent, action groups,
# or alias resources are required.  Tool definitions and dispatch happen
# in-process inside the Lambda.
#
# The IAM permission for bedrock:InvokeModel is granted in lambda.tf.

