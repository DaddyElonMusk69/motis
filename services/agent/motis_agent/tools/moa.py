"""
Motis Mixture-of-Agents
=======================
Adapted from NousResearch/hermes-agent tools/mixture_of_agents_tool.py (MIT License)

Key changes vs. Hermes:
- Reference models pulled from UserContext.model_config instead of hardcoded OpenRouter list
- No hardcoded OPENROUTER_API_KEY requirement — uses user's BYOM API key + base URL
- Fully async-native (was already async in Hermes, cleaned up)
- Result returned as dict (not JSON string) for consistency with other tools

Design (identical to Hermes MoA paper implementation):
  Layer 1: N reference models generate diverse responses in parallel (asyncio.gather)
  Layer 2: Aggregator model synthesizes into a single high-quality response

When to use: hard analytical problems where multiple model perspectives improve quality.
For financial analysis from multiple *expert roles*, use ResearchOperator instead.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from openai import AsyncOpenAI

from motis_agent.context import UserContext

logger = logging.getLogger(__name__)

# From Hermes mixture_of_agents_tool.py (paper defaults)
REFERENCE_TEMPERATURE = 0.6
AGGREGATOR_TEMPERATURE = 0.4
MIN_SUCCESSFUL_REFERENCES = 1

AGGREGATOR_SYSTEM_PROMPT = (
    "You have been provided with a set of responses from various AI models to the latest user query. "
    "Your task is to synthesize these responses into a single, high-quality response. "
    "Critically evaluate the information provided, recognizing that some may be biased or incorrect. "
    "Your response should not simply replicate the given answers but offer a refined, accurate, and "
    "comprehensive reply. Ensure your response is well-structured, coherent, and accurate.\n\n"
    "Responses from models:"
)


async def motis_mixture_of_agents(
    prompt: str,
    ctx: UserContext,
    reference_models: list[str] | None = None,
    aggregator_model: str | None = None,
) -> dict:
    """
    Process a complex query using Mixture-of-Agents methodology.
    Adapted from Hermes mixture_of_agents_tool().

    Uses the user's configured BYOM endpoint for all model calls.
    If the user has multiple models configured, all are used as reference models.
    If only one model is configured, it serves as both reference and aggregator
    (single-model MoA degrades gracefully to a high-temperature then low-temperature call).
    """
    model_cfg = ctx.model_config
    client = AsyncOpenAI(api_key=model_cfg.api_key, base_url=model_cfg.base_url)

    # Default: use the user's configured model for both reference and aggregation
    # If they've configured additional models, use those as reference models
    ref_models = reference_models or model_cfg.reference_models or [model_cfg.model]
    agg_model = aggregator_model or model_cfg.model

    start = time.monotonic()

    logger.info("MoA: %d reference models, aggregator=%s", len(ref_models), agg_model)

    # Layer 1: Reference models in parallel
    ref_results = await asyncio.gather(*[
        _call_reference_model(client, model, prompt)
        for model in ref_models
    ], return_exceptions=True)

    successful = [r for r in ref_results if isinstance(r, str) and r]
    failed = len(ref_results) - len(successful)

    if len(successful) < MIN_SUCCESSFUL_REFERENCES:
        return {
            "success": False,
            "response": "MoA: not enough reference models responded successfully.",
            "error": f"{failed}/{len(ref_models)} reference models failed.",
        }

    if failed > 0:
        logger.warning("MoA: %d/%d reference models failed", failed, len(ref_models))

    # Layer 2: Aggregator synthesizes
    numbered = "\n\n".join(f"{i+1}. {r}" for i, r in enumerate(successful))
    agg_system = f"{AGGREGATOR_SYSTEM_PROMPT}\n\n{numbered}"

    try:
        agg_response = await client.chat.completions.create(
            model=agg_model,
            messages=[
                {"role": "system", "content": agg_system},
                {"role": "user", "content": prompt},
            ],
            temperature=AGGREGATOR_TEMPERATURE,
        )
        final = agg_response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("MoA aggregator failed: %s", exc)
        # Degrade: return best single reference response
        final = successful[0] if successful else ""

    duration = round(time.monotonic() - start, 2)
    return {
        "success": bool(final),
        "response": final,
        "models_used": {"reference_models": ref_models, "aggregator_model": agg_model},
        "duration_seconds": duration,
    }


async def _call_reference_model(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    max_retries: int = 3,
) -> str | None:
    """
    Call a single reference model with retry + exponential backoff.
    Adapted from Hermes _run_reference_model_safe().
    Returns the response text, or None on failure.
    """
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=REFERENCE_TEMPERATURE,
            )
            content = response.choices[0].message.content or ""
            if content:
                return content
            logger.warning("Model %s returned empty content (attempt %d)", model, attempt + 1)
        except Exception as exc:
            logger.warning("Model %s errored (attempt %d): %s", model, attempt + 1, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(min(2 ** attempt, 16))

    return None
