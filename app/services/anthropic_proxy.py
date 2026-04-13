"""
Anthropic API proxy. Holds the server-side API key. Computes cost.

Pricing as of 2025 (update as needed):
- claude-sonnet-4-5 / sonnet-4-6: $3/M input, $15/M output
- claude-opus-4-6: $15/M input, $75/M output
- claude-haiku-4-5: $1/M input, $5/M output
"""
from typing import Any
import httpx
from app.core.config import settings


# USD per 1M tokens (input, output)
MODEL_PRICING = {
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    # fallback
    "default": (3.00, 15.00),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = input_tokens / 1_000_000 * pricing[0]
    output_cost = output_tokens / 1_000_000 * pricing[1]
    return round(input_cost + output_cost, 6)


async def call_anthropic(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Call Anthropic /v1/messages endpoint. Returns:
    {
        "content": str (joined text blocks),
        "input_tokens": int,
        "output_tokens": int,
        "cost_usd": float,
        "model": str,
        "stop_reason": str,
    }
    Raises httpx errors on network/API failures.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    model = model or settings.ANTHROPIC_MODEL_DEFAULT
    max_tokens = max_tokens or settings.ANTHROPIC_MAX_TOKENS

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract text
    text_parts = [c.get("text", "") for c in data.get("content", []) if c.get("type") == "text"]
    content = "\n".join(text_parts)

    usage = data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = compute_cost(model, input_tokens, output_tokens)

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model": model,
        "stop_reason": data.get("stop_reason", ""),
    }
