"""Claude API client for content generation."""

import anthropic
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()


class LLMError(Exception):
    """Error during LLM API call."""

    pass


class ClaudeClient:
    """Client for Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        """Initialize the Claude client.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        if not api_key:
            raise LLMError(
                "Anthropic API key not provided. "
                "Set ANTHROPIC_API_KEY environment variable or pass --api-key."
            )

        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate content using Claude.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text response
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            if message.content and len(message.content) > 0:
                return message.content[0].text

            raise LLMError("Empty response from Claude API")

        except anthropic.APIConnectionError as e:
            raise LLMError(f"Failed to connect to Anthropic API: {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMError(f"Rate limit exceeded: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"API error: {e}") from e
