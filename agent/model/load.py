"""Model configuration for the One-Click Report Analysis Agent."""

from strands.models import BedrockModel


def load_model() -> BedrockModel:
    """Load the Bedrock model provider for Claude."""
    return BedrockModel(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        streaming=True,
    )
