# Home Assistant Proxy

Narrow Home Assistant proxy API for GPT Actions.

The project goal is to let GPT inspect Home Assistant state and prepare safe configuration changes without giving GPT direct access to the Home Assistant token, shell, secrets, or the full `/config` directory.

## Current Stage

The codebase is currently through Stage 5 for the core proxy workflow, with SFTP write support implemented in the file backend.

Implemented:

- FastAPI application skeleton and Bearer API key authentication;
- Dockerfile and Docker Compose deployment for Windows Docker Desktop;
- mounted secret-file configuration for Docker deployments;
- Cloudflare Tunnel container wiring for a public Custom GPT Actions hostname;
- `/health` and `/capabilities`;
- Home Assistant read endpoints for config, entities, automations, and scripts;
- file list/read/search/metadata endpoints with `/config/...` API paths;
- strict file path allowlist and forbidden path policy;
- local file backend with read/write/delete;
- SFTP file backend with read/list/stat/write/delete;
- draft creation, diff preview, YAML validation, and base hash checks;
- apply and rollback with backups and audit records in SQLite;
- public audit log read endpoints;
- Home Assistant config check through `POST /api/config/core/check_config`;
- quick reload and selective automation/script reload endpoints;
- post-apply config check and quick reload;
- unit tests for the implemented core workflow.

Not implemented yet:

- rate limiting and request body size limiting;
- structured request logging and secret redaction;
- real integration smoke tests against the laptop/Home Assistant/SFTP environment.

Intentional v1 decision:

- `/ha/restart` is not implemented. Restart is manual only.

## Local Development

Install dependencies:

```powershell
uv sync --dev
```

Run tests:

```powershell
uv run pytest
```

Run the app:

```powershell
uv run uvicorn homeassistant_proxy.main:create_app --factory --reload
```

## Docker + Custom GPT Deployment

Start with:

- `docs/deployment_docker_cloudflare.md`
- `docs/custom_gpt_setup.md`
- `docs/custom_gpt_instructions.md`
- `docs/gpt_action_openapi.json`

The Docker deployment uses the SFTP backend and mounted secret files. Local file access is kept for tests and development.

Export the GPT Action schema for your real public URL:

```powershell
uv run python scripts\export_openapi.py `
  --server-url https://ha-gpt.example.com `
  --output docs\gpt_action_openapi.json
```

## Documentation

Start with `AGENTS.md`, then read the files under `docs/`.
