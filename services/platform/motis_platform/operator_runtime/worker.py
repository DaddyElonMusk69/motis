"""
Operator runtime — Celery workers that execute operator ticks.

Each live/paper operator is scheduled by Celery Beat based on its trigger_config.
Workers restore LangGraph state from Redis, run one tick, and save state back.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from celery import Celery

from motis_platform.operator_runtime.executor import OperatorExecutor

log = logging.getLogger(__name__)

app = Celery("motis_operator_runtime")
app.config_from_object("motis_platform.operator_runtime.celery_config")


@app.task(name="run_operator_tick", bind=True, max_retries=3)
def run_operator_tick(self, operator_id: str):
    """
    Execute one tick of an operator.
    Called by Celery Beat on the operator's configured schedule.
    """
    try:
        asyncio.get_event_loop().run_until_complete(
            _async_run_tick(UUID(operator_id))
        )
    except Exception as exc:
        log.error(f"Operator tick failed for {operator_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


async def _async_run_tick(operator_id: UUID):
    executor = OperatorExecutor()
    await executor.run_tick(operator_id)
