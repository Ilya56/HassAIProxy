# Architecture

## Selected Model

Use this integration model:

```text
Custom GPT with Actions
-> HA Proxy API
-> Home Assistant REST API + limited file layer
```

Reasons:

- GPT Actions work through an external API described by an OpenAPI schema and protected by API key or OAuth authentication.
- Home Assistant provides a REST API with Bearer token authentication.
- Home Assistant can check configuration during reload or restart, and quick reload is suitable for many YAML changes without a full restart.

## Recommended Stack

Use:

- Python 3.12+ and FastAPI;
- Pydantic for strict request and response schemas;
- httpx for Home Assistant API calls;
- ruamel.yaml for careful YAML handling;
- SQLite for draft changes and audit logs;
- uvicorn as the ASGI server;
- pytest for automated tests;
- structlog or standard JSON logging;
- Caddy or Nginx as a reverse proxy in front of the service.

FastAPI is a strong fit because OpenAPI generation is central to GPT Actions. For this narrow and security-sensitive domain, predictable contracts matter more than maximum flexibility.

## Deployment Direction

Home Assistant currently runs in Hyper-V HA OS on a laptop. The preferred first deployment is a separate service outside HA OS:

- on the Windows host; or
- in a lightweight Linux VM/container next to HA OS.

Benefits:

- does not pollute HA OS;
- easier updates and rollback;
- better control over filesystem and token access;
- cleaner responsibility boundaries.

The alternative is a Home Assistant add-on.

Benefits:

- closer to the Home Assistant ecosystem;
- convenient once the service is mature.

Tradeoffs:

- tighter coupling;
- slightly harder development and debugging;
- weaker separation of responsibilities.

For the first iteration, prefer a separate service outside HA OS.

## Components

### GPT Layer

Uses GPT Actions and calls only the proxy API.

### HA Proxy API

The main control layer. It owns:

- authentication;
- action authorization;
- path allowlist enforcement;
- file reads and writes;
- Home Assistant API calls;
- draft workflow;
- diff generation;
- validation;
- audit logging;
- rollback.

### Home Assistant API Layer

Used only by the proxy service. The Home Assistant token must not be exposed to GPT.

### File Access Layer

Provides access to a limited set of `/config` files. It must resolve paths safely before every read or write.

### Storage Layer

Stores drafts, file versions, backups metadata, and audit log entries.

## Access to `/config`

The best long-term approach is to expose `/config` to the proxy as a read/write volume only inside a trusted environment.

If the proxy runs outside HA OS, options include:

- exporting configuration through Samba or NFS and mounting it read/write;
- synchronizing a separate working folder;
- working only through the dedicated `packages/ai` folder.

The safest initial compromise is:

- write access only to `/config/packages/ai/`;
- read-only access to main files.

After the workflow is stable, write access can be expanded to `automations.yaml` and `scripts.yaml`.

## Deployment Notes

For v1:

- run the proxy outside HA OS but close to it;
- prefer a separate container or small service next to Home Assistant;
- expose `/config` through a controlled mount;
- place a reverse proxy in front of the application;
- use HTTPS for external access only when needed.
