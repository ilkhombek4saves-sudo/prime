from __future__ import annotations

from app.persistence.models import ProviderType
from app.services.token_optimizer import TokenOptimizationService


def test_token_optimizer_trims_history_and_caps_output():
    svc = TokenOptimizationService()
    history = [
        {"role": "user", "content": "u" * 2400},
        {"role": "assistant", "content": "a" * 2200},
        {"role": "user", "content": "x" * 2100},
        {"role": "assistant", "content": "y" * 2300},
    ]
    config = {
        "default_model": "gpt-4o",
        "api_key": "x",
        "models": {
            "gpt-4o": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03,
            }
        },
        "token_optimization": {
            "input_budget_tokens": 500,
            "max_output_tokens": 300,
            "max_message_tokens": 180,
        },
    }
    plan = svc.optimize_request(
        provider_type=ProviderType.OpenAI,
        provider_name="openai_default",
        provider_config=config,
        system="You are a concise assistant",
        history=history,
        user_message="answer briefly",
    )

    assert plan.max_output_tokens == 300
    assert plan.kept_history_messages < len(history)
    assert plan.dropped_history_messages > 0
    assert plan.estimated_input_tokens <= 500
    assert plan.estimated_cost_usd > 0


def test_token_optimizer_auto_routes_simple_prompt_to_cheaper_model():
    svc = TokenOptimizationService()
    config = {
        "default_model": "gpt-4o",
        "api_key": "x",
        "models": {
            "gpt-4o": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03,
            },
            "gpt-4o-mini": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
            },
        },
        "token_optimization": {"auto_route_enabled": True},
    }
    plan = svc.optimize_request(
        provider_type=ProviderType.OpenAI,
        provider_name="openai_default",
        provider_config=config,
        system=None,
        history=[],
        user_message="translate: hello -> spanish",
    )
    assert plan.model == "gpt-4o-mini"


def test_token_optimizer_keeps_default_model_for_complex_prompt():
    svc = TokenOptimizationService()
    config = {
        "default_model": "gpt-4o",
        "api_key": "x",
        "models": {
            "gpt-4o": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03,
            },
            "gpt-4o-mini": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
            },
        },
        "token_optimization": {"auto_route_enabled": True},
    }
    plan = svc.optimize_request(
        provider_type=ProviderType.OpenAI,
        provider_name="openai_default",
        provider_config=config,
        system=None,
        history=[],
        user_message="Design an architecture for a migration pipeline with SQL + Python and tests",
    )
    assert plan.model == "gpt-4o"
