from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistence.models import Binding


@dataclass
class BindingScore:
    specificity: int
    priority: int
    created_at: datetime


class BindingResolver:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _score_candidate(
        binding: Binding,
        account_id: str | None,
        peer: str | None,
    ) -> BindingScore | None:
        specificity = 0

        if binding.account_id is not None:
            if account_id is None or binding.account_id != account_id:
                return None
            specificity += 2

        if binding.peer is not None:
            if peer is None or binding.peer != peer:
                return None
            specificity += 1

        return BindingScore(
            specificity=specificity,
            priority=binding.priority,
            created_at=binding.created_at,
        )

    @classmethod
    def select_best(
        cls,
        candidates: Iterable[Binding],
        account_id: str | None,
        peer: str | None,
    ) -> Binding | None:
        scored: list[tuple[BindingScore, Binding]] = []
        for item in candidates:
            score = cls._score_candidate(item, account_id=account_id, peer=peer)
            if score is None:
                continue
            scored.append((score, item))

        if not scored:
            return None

        scored.sort(
            key=lambda pair: (
                pair[0].specificity,
                pair[0].priority,
                pair[0].created_at,
            ),
            reverse=True,
        )
        return scored[0][1]

    def resolve(
        self,
        *,
        channel: str,
        account_id: str | None,
        peer: str | None,
        bot_id: UUID | None = None,
    ) -> Binding | None:
        query = self.db.query(Binding).filter(Binding.channel == channel, Binding.active.is_(True))
        if bot_id is not None:
            query = query.filter((Binding.bot_id == bot_id) | (Binding.bot_id.is_(None)))

        candidates = query.all()
        return self.select_best(candidates=candidates, account_id=account_id, peer=peer)
