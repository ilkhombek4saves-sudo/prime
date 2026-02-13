# Contributing

## Add new provider
1. Create a class in `backend/app/providers/` inheriting `ServiceProvider`.
2. Implement `validate_config`, `estimate_cost`, and capability methods.
3. Register provider type in `backend/app/providers/registry.py`.
4. Add provider config template in `config/providers.yaml`.

## Add new plugin
1. Create plugin class in `backend/app/plugins/` inheriting `PluginBase`.
2. Define `input_schema`, `permissions`, and `run()`.
3. Register plugin in `backend/app/plugins/registry.py`.
4. Add plugin config template in `config/plugins.yaml`.

## Add new bot
1. Add entry to `config/bots.yaml` or use Admin UI Bots page.
2. Ensure `allowed_user_ids` and plugin mappings are valid.

## Quality gates
- Run formatter/lint/tests before PR.
- Keep structured logging fields intact.
- Document API/behavior changes in `docs/`.
