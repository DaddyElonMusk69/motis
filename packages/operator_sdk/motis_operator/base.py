from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar
from uuid import UUID

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import StateGraph
from pydantic import BaseModel

from motis_shared.models.operator import OperatorModel, RiskConfig

S = TypeVar("S", bound=BaseModel)


class OperatorBase(ABC):
    """
    Base class for all Motis Operators.

    An Operator is a deterministic LangGraph StateGraph where model reasoning
    is used only at explicitly designated nodes. All other nodes are pure
    Python — predictable, testable, auditable.

    Subclasses must implement:
        - build_graph() → returns a compiled LangGraph graph
        - state_schema() → returns the TypedDict/Pydantic class for state

    Example usage:
        class MyTrendOperator(OperatorBase):
            def state_schema(self):
                return TrendOperatorState

            def build_graph(self):
                graph = StateGraph(TrendOperatorState)
                graph.add_node("fetch_data", self._fetch_data)
                graph.add_node("generate_signal", self._generate_signal)  # model node
                graph.add_node("risk_check", self._risk_check)
                graph.add_node("execute", self._execute)
                graph.set_entry_point("fetch_data")
                graph.add_edge("fetch_data", "generate_signal")
                graph.add_edge("generate_signal", "risk_check")
                graph.add_edge("risk_check", "execute")
                return graph.compile(checkpointer=self.checkpointer)
    """

    def __init__(
        self,
        model: OperatorModel,
        redis_url: str,
        mcp_client: Any,  # MotisMCPClient
    ):
        self.model = model
        self.operator_id = model.id
        self.user_id = model.user_id
        self.risk_config = model.risk_config
        self.mcp_client = mcp_client

        # LangGraph checkpointer (Redis-backed for persistence)
        self.checkpointer = AsyncRedisSaver.from_conn_string(
            redis_url,
            ttl={"default": 60 * 60 * 24 * 30},  # 30 days
        )
        self._graph = None

    @abstractmethod
    def build_graph(self) -> Any:
        """Return a compiled LangGraph graph."""
        ...

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self.build_graph()
        return self._graph

    @property
    def thread_id(self) -> str:
        """Unique LangGraph thread ID for this operator instance."""
        return f"operator:{self.operator_id}"

    async def tick(self, input_data: Optional[dict] = None) -> dict:
        """
        Run one tick of the operator graph.
        State is automatically restored from Redis checkpoint.
        """
        config = {
            "configurable": {
                "thread_id": self.thread_id,
                "user_id": str(self.user_id),
                "operator_id": str(self.operator_id),
            }
        }
        result = await self.graph.ainvoke(
            input=input_data or {},
            config=config,
        )
        return result

    async def get_state(self) -> dict:
        """Retrieve current persisted state from Redis."""
        config = {"configurable": {"thread_id": self.thread_id}}
        snapshot = await self.graph.aget_state(config)
        return dict(snapshot.values) if snapshot else {}

    # ─── Risk enforcement helpers (called by risk_check nodes) ───────────────

    def check_position_limit(self, proposed_size_usd: float, current_aum: float) -> bool:
        """Returns True if proposed trade is within risk config limits."""
        max_size = current_aum * (self.risk_config.max_position_size_pct / 100)
        return proposed_size_usd <= max_size

    def check_daily_loss(self, daily_pnl_usd: float, current_aum: float) -> bool:
        """Returns True if daily loss hasn't breached the kill-switch threshold."""
        max_loss = current_aum * (self.risk_config.max_daily_loss_pct / 100)
        return daily_pnl_usd > -max_loss

    @classmethod
    def from_spec(
        cls,
        spec_json: str,
        model: OperatorModel,
        redis_url: str,
        mcp_client: Any,
    ) -> "OperatorBase":
        """Deserialize an operator from its stored graph spec JSON."""
        # TODO: dynamic operator loading from serialized spec
        raise NotImplementedError("Dynamic spec loading will be implemented in Phase 1")
