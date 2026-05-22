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
- optional Sentry monitoring for unhandled exceptions, handled 5xx API errors, and sampled performance traces;
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

## Sentry Monitoring

Set `SENTRY_DSN` to enable Sentry. The SDK is initialized before the FastAPI app is created.

Useful settings:

```text
SENTRY_DSN=https://...
SENTRY_RELEASE=homeassistant-proxy@0.1.0
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_SEND_DEFAULT_PII=false
SENTRY_DEBUG_ROUTE_ENABLED=false
```

Handled `ApiError` responses with status `500` and above are sent to Sentry, so transport failures such as `502 files.remote_transport_error` are visible even when the API returns a clean JSON error response. Request bodies, cookies, auth headers, tokens, keys, secrets, and passphrases are redacted or omitted.

For a one-time verification, set `SENTRY_DEBUG_ROUTE_ENABLED=true`, restart the app, open `/sentry-debug`, confirm the event appears in Sentry, then set it back to `false`.

## Documentation

Start with `AGENTS.md`, then read the files under `docs/`.
