"""
Cost tracking — records per-request costs and provides analytics.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app.persistence.models import CostRecord

logger = logging.getLogger(__name__)


class CostTracker:
    def record(
        self,
        db: DbSession,
        *,
        org_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        provider_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        channel: str = "telegram",
    ) -> CostRecord:
        rec = CostRecord(
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id,
            provider_id=provider_id,
            session_id=session_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            channel=channel,
        )
        db.add(rec)
        db.commit()
        return rec

    def get_summary(
        self,
        db: DbSession,
        *,
        org_id: uuid.UUID | None = None,
        days: int = 30,
    ) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        q = db.query(
            func.count(CostRecord.id).label("requests"),
            func.coalesce(func.sum(CostRecord.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(CostRecord.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(CostRecord.cost_usd), 0).label("total_cost_usd"),
        ).filter(CostRecord.created_at >= since)
        if org_id:
            q = q.filter(CostRecord.org_id == org_id)
        row = q.one()
        return {
            "period_days": days,
            "requests": row.requests,
            "input_tokens": int(row.input_tokens),
            "output_tokens": int(row.output_tokens),
            "total_cost_usd": round(float(row.total_cost_usd), 6),
        }

    def get_by_agent(
        self,
        db: DbSession,
        *,
        org_id: uuid.UUID | None = None,
        days: int = 30,
    ) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        q = (
            db.query(
                CostRecord.agent_id,
                func.count(CostRecord.id).label("requests"),
                func.coalesce(func.sum(CostRecord.cost_usd), 0).label("cost"),
            )
            .filter(CostRecord.created_at >= since)
            .group_by(CostRecord.agent_id)
            .order_by(func.sum(CostRecord.cost_usd).desc())
        )
        if org_id:
            q = q.filter(CostRecord.org_id == org_id)
        return [
            {"agent_id": str(r.agent_id), "requests": r.requests, "cost_usd": round(float(r.cost), 6)}
            for r in q.all()
        ]

    def get_by_model(
        self,
        db: DbSession,
        *,
        days: int = 30,
    ) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(
                CostRecord.model,
                func.count(CostRecord.id).label("requests"),
                func.coalesce(func.sum(CostRecord.input_tokens), 0).label("inp"),
                func.coalesce(func.sum(CostRecord.output_tokens), 0).label("out"),
                func.coalesce(func.sum(CostRecord.cost_usd), 0).label("cost"),
            )
            .filter(CostRecord.created_at >= since)
            .group_by(CostRecord.model)
            .order_by(func.sum(CostRecord.cost_usd).desc())
            .all()
        )
        return [
            {
                "model": r.model,
                "requests": r.requests,
                "input_tokens": int(r.inp),
                "output_tokens": int(r.out),
                "cost_usd": round(float(r.cost), 6),
            }
            for r in rows
        ]
