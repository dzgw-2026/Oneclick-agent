# --- Bedrock / AgentCore ---
#
# The Strands agent runs on AgentCore Runtime, deployed via the AgentCore CLI
# (agentcore deploy). No Terraform-managed Bedrock resources are needed.
#
# The AgentCore CLI handles:
#   - Agent Runtime provisioning
#   - IAM role for the agent (Bedrock model access + DynamoDB access)
#   - CloudFormation stack via CDK
#
# The intake Lambda's permission to invoke the agent runtime is in lambda.tf.

