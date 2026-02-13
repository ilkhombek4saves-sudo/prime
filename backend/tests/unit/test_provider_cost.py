from app.providers.glm_provider import GLMProvider


def test_glm_cost_estimate():
    provider = GLMProvider(
        name="glm_default",
        config={
            "api_key": "x",
            "default_model": "glm-4.7",
            "models": {"glm-4.7": {"cost_per_1m_input": 0.6, "cost_per_1m_output": 2.2}},
        },
    )
    provider.validate_config()
    cost = provider.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000)
    assert round(cost, 2) == 2.8
