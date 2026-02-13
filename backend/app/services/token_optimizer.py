from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.persistence.models import ProviderType
from app.services.cost_service import estimate_provider_cost

DEFAULT_INPUT_BUDGET_TOKENS = 6000
DEFAULT_OUTPUT_MIN_TOKENS = 192
DEFAULT_OUTPUT_MAX_TOKENS = 1024
DEFAULT_MESSAGE_TOKEN_CAP = 1200
DEFAULT_TOKEN_BUFFER = 96
MIN_TRUNCATION_TOKENS = 48


@dataclass
class TokenOptimizationPlan:
    model: str
    max_output_tokens: int
    history: list[dict[str, str]]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    original_history_messages: int
    kept_history_messages: int
    dropped_history_messages: int
    truncated_messages: int
    input_budget_tokens: int
    notes: list[str] = field(default_factory=list)

    def as_meta(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
            "input_budget_tokens": self.input_budget_tokens,
            "history": {
                "original_messages": self.original_history_messages,
                "kept_messages": self.kept_history_messages,
                "dropped_messages": self.dropped_history_messages,
                "truncated_messages": self.truncated_messages,
            },
            "notes": self.notes,
        }


class TokenOptimizationService:
    """Heuristic token optimizer for context pruning + cost-aware model selection."""

    _COMPLEX_PROMPT_RE = re.compile(
        r"```|\b(architect|migration|benchmark|optimiz|refactor|debug|deploy|pipeline|sql|python|typescript)\b",
        re.IGNORECASE,
    )
    _COMPLEX_PROMPT_RU_RE = re.compile(
        r"(архитект|миграц|оптимиз|рефактор|дебаг|деплой|пайплайн|тест|документац|поэтапн|подробно|код)",
        re.IGNORECASE,
    )
    _SHORT_ANSWER_HINT_RE = re.compile(
        r"\b(short|brief|tldr|one[- ]line|кратко|коротко|в двух словах)\b",
        re.IGNORECASE,
    )
    _LONG_ANSWER_HINT_RE = re.compile(
        r"\b(detailed|deep|step[- ]by[- ]step|long|подробно|развернуто|пошагово)\b",
        re.IGNORECASE,
    )

    def optimize_request(
        self,
        *,
        provider_type: ProviderType | str,
        provider_name: str,
        provider_config: dict[str, Any],
        system: str | None,
        history: list[dict[str, Any]] | None,
        user_message: str,
    ) -> TokenOptimizationPlan:
        cfg = provider_config.get("token_optimization") or {}
        models_cfg = provider_config.get("models") or {}
        default_model = str(
            provider_config.get("default_model")
            or next(iter(models_cfg.keys()), "gpt-4o")
        )
        model = self._select_model(default_model, models_cfg, cfg, user_message)
        model_cfg = models_cfg.get(model, {})

        model_max_output = self._as_int(
            model_cfg.get("max_tokens"), DEFAULT_OUTPUT_MAX_TOKENS
        )
        max_output_tokens = self._choose_output_budget(
            user_message=user_message,
            model_max_output=model_max_output,
            cfg=cfg,
        )
        input_budget_tokens = self._as_int(
            cfg.get("input_budget_tokens")
            or model_cfg.get("input_budget_tokens")
            or model_cfg.get("context_window"),
            max(DEFAULT_INPUT_BUDGET_TOKENS, model_max_output * 3),
        )

        trimmed_history, dropped, truncated = self._trim_history_to_budget(
            history=history or [],
            system=system,
            user_message=user_message,
            input_budget_tokens=input_budget_tokens,
            cfg=cfg,
        )

        estimated_input_tokens = self._estimate_input_tokens(
            system=system,
            history=trimmed_history,
            user_message=user_message,
        )
        estimated_output_tokens = max_output_tokens

        notes: list[str] = []
        if model != default_model:
            notes.append(f"model_routed:{default_model}->{model}")
        if dropped > 0:
            notes.append(f"history_dropped:{dropped}")
        if truncated > 0:
            notes.append(f"history_truncated:{truncated}")

        estimated_cost_usd = self.estimate_cost(
            provider_type=provider_type,
            provider_name=provider_name,
            provider_config=provider_config,
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens,
        )

        return TokenOptimizationPlan(
            model=model,
            max_output_tokens=max_output_tokens,
            history=trimmed_history,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            original_history_messages=len(history or []),
            kept_history_messages=len(trimmed_history),
            dropped_history_messages=dropped,
            truncated_messages=truncated,
            input_budget_tokens=input_budget_tokens,
            notes=notes,
        )

    def estimate_text_tokens(self, text: str | None) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def estimate_cost(
        self,
        *,
        provider_type: ProviderType | str,
        provider_name: str,
        provider_config: dict[str, Any],
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        normalized = self._normalize_provider_type(provider_type)
        if not normalized:
            return 0.0
        try:
            return estimate_provider_cost(
                normalized,
                provider_name,
                provider_config,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            return 0.0

    def _select_model(
        self,
        default_model: str,
        models_cfg: dict[str, Any],
        cfg: dict[str, Any],
        user_message: str,
    ) -> str:
        if not models_cfg:
            return default_model
        if not bool(cfg.get("auto_route_enabled", False)):
            return default_model

        is_simple = self._is_simple_prompt(user_message)
        mapped_routes = cfg.get("route_by_complexity") or {}
        mapped_model = mapped_routes.get("simple" if is_simple else "complex")
        if isinstance(mapped_model, str) and mapped_model in models_cfg:
            return mapped_model

        if is_simple:
            cheapest = self._find_cheapest_model(models_cfg)
            if cheapest:
                return cheapest
        return default_model

    def _find_cheapest_model(self, models_cfg: dict[str, Any]) -> str | None:
        best_model = None
        best_score = float("inf")
        for model_name, model_cfg_raw in models_cfg.items():
            model_cfg = model_cfg_raw or {}
            score = self._model_cost_score(model_cfg)
            if score < best_score:
                best_score = score
                best_model = model_name
        return best_model

    def _model_cost_score(self, model_cfg: dict[str, Any]) -> float:
        input_1m = float(
            model_cfg.get(
                "cost_per_1m_input",
                float(model_cfg.get("cost_per_1k_input", 0.0)) * 1000.0,
            )
        )
        output_1m = float(
            model_cfg.get(
                "cost_per_1m_output",
                float(model_cfg.get("cost_per_1k_output", 0.0)) * 1000.0,
            )
        )
        return input_1m + output_1m

    def _choose_output_budget(
        self,
        *,
        user_message: str,
        model_max_output: int,
        cfg: dict[str, Any],
    ) -> int:
        explicit_cap = cfg.get("max_output_tokens")
        if explicit_cap is not None:
            return self._clamp(
                self._as_int(explicit_cap, DEFAULT_OUTPUT_MAX_TOKENS),
                low=64,
                high=model_max_output,
            )

        user_tokens = self.estimate_text_tokens(user_message)
        ratio = float(cfg.get("output_to_input_ratio", 1.8))
        dynamic = int(user_tokens * ratio)
        dynamic = self._clamp(
            dynamic,
            low=DEFAULT_OUTPUT_MIN_TOKENS,
            high=min(DEFAULT_OUTPUT_MAX_TOKENS, model_max_output),
        )
        if self._SHORT_ANSWER_HINT_RE.search(user_message):
            dynamic = min(dynamic, 256)
        if self._LONG_ANSWER_HINT_RE.search(user_message):
            dynamic = max(dynamic, 1024)
        return self._clamp(dynamic, low=64, high=model_max_output)

    def _trim_history_to_budget(
        self,
        *,
        history: list[dict[str, Any]],
        system: str | None,
        user_message: str,
        input_budget_tokens: int,
        cfg: dict[str, Any],
    ) -> tuple[list[dict[str, str]], int, int]:
        max_message_tokens = self._as_int(
            cfg.get("max_message_tokens"), DEFAULT_MESSAGE_TOKEN_CAP
        )

        base_input_tokens = (
            self.estimate_text_tokens(system)
            + self.estimate_text_tokens(user_message)
            + self._role_overhead("system")
            + self._role_overhead("user")
            + DEFAULT_TOKEN_BUFFER
        )
        remaining = max(input_budget_tokens - base_input_tokens, 0)
        if remaining <= 0:
            return [], len(history), 0

        picked_reversed: list[dict[str, str]] = []
        dropped = 0
        truncated = 0

        for raw in reversed(history):
            role = str(raw.get("role") or "user")
            if role not in {"user", "assistant"}:
                continue
            content = str(raw.get("content") or "")
            content = self._truncate_text_to_tokens(content, max_message_tokens)
            message_tokens = self.estimate_text_tokens(content) + self._role_overhead(role)

            if message_tokens <= remaining:
                picked_reversed.append({"role": role, "content": content})
                remaining -= message_tokens
                continue

            allowed_content_tokens = max(remaining - self._role_overhead(role), 0)
            if allowed_content_tokens >= MIN_TRUNCATION_TOKENS:
                clipped = self._truncate_text_to_tokens(content, allowed_content_tokens)
                if clipped:
                    picked_reversed.append({"role": role, "content": clipped})
                    truncated += 1
                    remaining = 0
                    break
            dropped += 1

        kept = list(reversed(picked_reversed))
        dropped += max(0, len(history) - len(kept) - dropped)
        return kept, dropped, truncated

    def _estimate_input_tokens(
        self,
        *,
        system: str | None,
        history: list[dict[str, str]],
        user_message: str,
    ) -> int:
        total = self.estimate_text_tokens(system) + self.estimate_text_tokens(user_message)
        total += self._role_overhead("system") + self._role_overhead("user")
        for item in history:
            total += self.estimate_text_tokens(item.get("content"))
            total += self._role_overhead(item.get("role", "user"))
        return total

    def _truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        estimated = self.estimate_text_tokens(text)
        if estimated <= max_tokens:
            return text
        max_chars = max_tokens * 4
        if max_chars <= 3:
            return ""
        return text[-max_chars:]

    def _is_simple_prompt(self, text: str) -> bool:
        if len(text) > 600:
            return False
        if text.count("\n") > 5:
            return False
        if self._COMPLEX_PROMPT_RE.search(text) or self._COMPLEX_PROMPT_RU_RE.search(text):
            return False
        return True

    def _normalize_provider_type(self, provider_type: ProviderType | str) -> ProviderType | None:
        if isinstance(provider_type, ProviderType):
            return provider_type
        raw = str(provider_type)
        if raw.startswith("ProviderType."):
            raw = raw.split(".", 1)[1]
        try:
            return ProviderType(raw)
        except Exception:
            return None

    @staticmethod
    def _role_overhead(role: str) -> int:
        if role == "system":
            return 10
        if role == "assistant":
            return 8
        return 8

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: int, *, low: int, high: int) -> int:
        return max(low, min(high, value))
