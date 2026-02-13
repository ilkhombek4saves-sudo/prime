from app.providers.registry import build_provider


def estimate_provider_cost(provider_type, provider_name: str, config: dict, input_tokens: int, output_tokens: int) -> float:
    provider = build_provider(provider_type, provider_name, config)
    return provider.estimate_cost(input_tokens=input_tokens, output_tokens=output_tokens)
