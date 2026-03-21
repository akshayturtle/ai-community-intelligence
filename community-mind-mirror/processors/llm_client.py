"""Shared Azure OpenAI async client with retry logic and token tracking."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog
from openai import AsyncAzureOpenAI, RateLimitError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_DEPLOYMENT_MINI,
)
from spending_tracker import record_spend, is_over_budget, PRICING

logger = structlog.get_logger()

_client: AsyncAzureOpenAI | None = None


@dataclass
class TokenUsage:
    """Accumulates token usage across multiple LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion
        self.calls += 1

    @property
    def estimated_cost_usd(self) -> float:
        """Rough estimate based on Azure OpenAI gpt-4o-mini pricing."""
        # gpt-4o-mini: ~$0.15/1M input, ~$0.60/1M output
        # gpt-4o:      ~$2.50/1M input, ~$10.00/1M output
        # Use blended mini estimate as conservative default
        input_cost = (self.prompt_tokens / 1_000_000) * 0.15
        output_cost = (self.completion_tokens / 1_000_000) * 0.60
        return input_cost + output_cost


def get_client() -> AsyncAzureOpenAI:
    """Lazy singleton for the Azure OpenAI async client."""
    global _client
    if _client is None:
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in .env"
            )
        _client = AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )
    return _client


def _get_deployment(model: str) -> str:
    """Map model alias to Azure deployment name."""
    if model == "mini":
        if not AZURE_OPENAI_DEPLOYMENT_MINI:
            raise RuntimeError("AZURE_OPENAI_DEPLOYMENT_MINI must be set in .env")
        return AZURE_OPENAI_DEPLOYMENT_MINI
    if not AZURE_OPENAI_DEPLOYMENT:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT must be set in .env")
    return AZURE_OPENAI_DEPLOYMENT


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers from LLM output."""
    text = text.strip()
    # Remove opening fence
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
)
async def call_llm(
    prompt: str,
    system_message: str = "You are a helpful assistant.",
    model: str = "default",
    temperature: float = 0.3,
    max_tokens: int = 2000,
    parse_json: bool = False,
    usage_tracker: TokenUsage | None = None,
) -> str | dict[str, Any]:
    """
    Call Azure OpenAI with retry logic.

    model="default" -> AZURE_OPENAI_DEPLOYMENT (gpt-4o)
    model="mini"    -> AZURE_OPENAI_DEPLOYMENT_MINI (gpt-4o-mini)
    parse_json=True -> strips markdown fences, parses JSON, returns dict
    """
    # Check budget before making the call
    if is_over_budget():
        raise RuntimeError("LLM spending cap reached — refusing new LLM calls")

    client = get_client()
    deployment = _get_deployment(model)

    response = await client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Track usage
    if response.usage and usage_tracker is not None:
        usage_tracker.add(
            prompt=response.usage.prompt_tokens,
            completion=response.usage.completion_tokens,
        )

    # Record spend to persistent tracker
    if response.usage:
        pricing_key = "gpt-4o-mini" if model == "mini" else "gpt-4o"
        prices = PRICING.get(pricing_key, PRICING["gpt-4o-mini"])
        cost = (
            (response.usage.prompt_tokens / 1_000_000) * prices["input"]
            + (response.usage.completion_tokens / 1_000_000) * prices["output"]
        )
        record_spend(
            phase=f"llm:{deployment}",
            cost_usd=cost,
            details=f"{response.usage.prompt_tokens}in+{response.usage.completion_tokens}out",
        )

    content = response.choices[0].message.content or ""

    if parse_json:
        cleaned = _strip_json_fences(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed",
                error=str(e),
                raw_content=content[:500],
            )
            raise

    return content
