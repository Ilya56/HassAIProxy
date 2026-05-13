# Home Assistant Proxy

Narrow Home Assistant proxy API for GPT Actions.

The project goal is to let GPT inspect Home Assistant state and prepare safe configuration changes without giving GPT direct access to the Home Assistant token, shell, secrets, or the full `/config` directory.

## Current Stage

Stage 1 has started with:

- FastAPI application skeleton;
- Bearer API key dependency;
- `/health`;
- `/capabilities`;
- `/ha/config`;
- Home Assistant REST client foundation;
- basic Pydantic response models;
- initial tests.

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

## Documentation

Start with `AGENTS.md`, then read the files under `docs/`.
