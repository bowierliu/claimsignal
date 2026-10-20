"""Provider adapters. Each translates the neutral agent types to one provider's wire format."""

from claims_copilot.agent.providers.anthropic import AnthropicProvider
from claims_copilot.agent.providers.openai import OpenAIProvider

__all__ = ["AnthropicProvider", "OpenAIProvider"]
