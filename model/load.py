"""Model configuration for the One-Click Report Analysis Agent."""

from strands.models import BedrockModel


def load_model() -> BedrockModel:
    """Load the Bedrock model provider for Claude."""
    return BedrockModel(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        streaming=True,
    )
