"""
Swarm runner — orchestrates multi-agent research teams.
Adapted from Vibe-Trading's 29 preset swarm system.

A swarm is a LangGraph multi-agent graph where each agent plays a specific role
(bull analyst, bear analyst, quant, macro, risk manager) and their outputs are
synthesized into a final research brief.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

PRESETS_DIR = Path(__file__).parent / "presets"


class SwarmRunner:
    """
    Runs a research swarm from a preset configuration.

    Usage:
        runner = SwarmRunner(model_base_url=..., model_api_key=..., model_name=...)
        async for event in runner.stream("Analyze BTC funding rate arb", "crypto_trading_desk"):
            print(event)
    """

    AVAILABLE_PRESETS = [
        "investment_committee",
        "global_equities_desk",
        "crypto_trading_desk",
        "earnings_research_desk",
        "macro_rates_fx_desk",
        "quant_strategy_desk",
        "technical_analysis_panel",
        "risk_committee",
        "global_allocation_committee",
        "defi_research_desk",
        "options_strategy_desk",
        "sector_rotation_desk",
        "factor_research_desk",
        "credit_analysis_desk",
        "onchain_intelligence_desk",
    ]

    def __init__(
        self,
        model_base_url: str,
        model_api_key: str,
        model_name: str,
    ):
        self.model_base_url = model_base_url
        self.model_api_key = model_api_key
        self.model_name = model_name

    def load_preset(self, preset_name: str) -> dict:
        """Load a swarm preset configuration from YAML."""
        if preset_name not in self.AVAILABLE_PRESETS:
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {self.AVAILABLE_PRESETS}"
            )
        preset_path = PRESETS_DIR / f"{preset_name}.yaml"
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        with open(preset_path) as f:
            return yaml.safe_load(f)

    async def run(
        self,
        prompt: str,
        preset: str,
        variables: Optional[dict] = None,
    ) -> dict:
        """Run a swarm and return the final synthesized result."""
        results = []
        async for event in self.stream(prompt, preset, variables):
            results.append(event)
        # Last substantive event is the synthesis
        synthesis = next(
            (e for e in reversed(results) if e.get("type") == "synthesis"),
            results[-1] if results else {}
        )
        return synthesis

    async def stream(
        self,
        prompt: str,
        preset: str,
        variables: Optional[dict] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream swarm execution events.
        Each event: { type, agent_name, content, timestamp }
        """
        config = self.load_preset(preset)
        agents = config.get("agents", [])

        # TODO: implement full LangGraph multi-agent graph
        # For now, sequential agent calls with streaming
        from datetime import datetime, timezone

        for agent_config in agents:
            yield {
                "type": "agent_start",
                "agent_name": agent_config["name"],
                "role": agent_config["role"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            # Agent reasoning will be implemented here using langchain_openai
            # with the user's BYOM config
            yield {
                "type": "agent_result",
                "agent_name": agent_config["name"],
                "content": f"[{agent_config['name']} analysis — to be implemented]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        yield {
            "type": "synthesis",
            "content": "[Swarm synthesis — to be implemented]",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
