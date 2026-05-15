# Implementation Plan

## Current Implementation Status

As of the current codebase:

- Stages 0 through 5 are implemented for the core workflow.
- SFTP is no longer read-only in code: the SFTP backend supports read, list, stat, write, and delete.
- SFTP writes use a same-directory temporary file followed by an overwrite/atomic rename request.
- Apply and rollback are backend-independent and can use either the local or SFTP backend.
- Apply performs local draft validation, writes the file, runs Home Assistant config check through
  `POST /api/config/core/check_config`, and performs quick reload when validation passes.
- Audit records are written to SQLite and exposed through `/audit/logs` and `/audit/logs/{log_id}`.
- `/ha/restart` is intentionally not implemented for v1; restart remains manual.
- The test suite covers the implemented unit-level behavior.

Still pending before connecting to ChatGPT:

- real SFTP/Home Assistant integration smoke test on the target laptop environment;
- generated OpenAPI schema from the live FastAPI app;
- Custom GPT Action setup;
- Stage 7 hardening, including rate limiting, request size limits, structured request logging,
  secret redaction, and operational token/key revocation docs.

## Stage 0: Design

Result:

- approved path allowlist;
- approved Home Assistant service allowlist;
- deployment decision;
- decision about `/config/packages/ai/`.

Artifacts:

- `docs/requirements.md`
- `docs/security_policy.md`
- `docs/api_contract_v1.yaml`

## Stage 1: Service Skeleton

Build:

- FastAPI project;
- health endpoint;
- capabilities endpoint;
- config loader;
- auth middleware;
- structured logging;
- Home Assistant REST API client.

Ready when:

- `/health` works;
- the proxy can read basic `/api/` information from Home Assistant.

## Stage 2: Read-Only Capabilities

Build:

- `GET /ha/entities`;
- `GET /ha/entities/{entity_id}`;
- `GET /ha/automations`;
- `GET /ha/scripts`;
- `GET /ha/config`;
- list/read/search for files;
- file metadata;
- path allowlist;
- file backend boundary with at least local filesystem support;
- optional SFTP read backend for Home Assistant OS deployments where `/config` is available through
  Advanced SSH & Web Terminal rather than a direct mount;
- hard rejection of everything outside the allowlist.

Ready when:

- GPT can ask about home state and read allowed configuration files.
- the file API returns stable `/config/...` paths regardless of backend.

## Stage 3: Draft Engine

Build:

- `drafts` table;
- create draft;
- diff preview;
- version hash;
- basic YAML validation.
- backend-independent file reads for base content and hashes.

Ready when:

- GPT can prepare a diff but cannot apply it yet.

## Stage 4: Apply Engine

Build:

- backup before write;
- `POST /drafts/{draft_id}/apply`;
- `POST /drafts/{draft_id}/rollback`;
- post-write validation;
- audit log.
- backend-independent writes, with local and SFTP behavior tested before enabling writes on SFTP.

Ready when:

- a file change can safely pass through the complete lifecycle.

## Stage 5: Home Assistant Config Operations

Build:

- config check;
- quick reload;
- selective reload for automations and scripts;
- restart as a separate rare endpoint.

Ready when:

- after applying a change, the service knows what should happen next.

## Stage 6: OpenAPI and GPT

Build:

- OpenAPI contract;
- Custom GPT action;
- Bearer/API key auth;
- tested operation IDs and clear endpoint descriptions.

Ready when:

- GPT can call the proxy through a defined action contract.

## Stage 7: Hardening

Build:

- rate limiting;
- path traversal tests;
- negative tests;
- remote file transport timeout and failure tests;
- token revoke and rotation procedure;
- emergency read-only mode.

Ready when:

- the service can be used remotely without reasonable fear that it will damage the Home Assistant configuration.

## Priority Order

Build first:

- read-only Home Assistant access;
- read-only file access;
- drafts and diffs;
- apply with backup;
- config check and reload.

Build later:

- selective editing of existing files;
- write access to `automations.yaml` and `scripts.yaml`;
- richer rollback endpoint/UI;
- richer risk analysis;
- smarter Jinja validation;
- automation generation templates;
- richer semantic search across configuration;
- library of common scenarios.
- web UI for draft and audit review;
- Git integration as an additional history layer.

## Recommended Starting MVP

Start with:

- FastAPI proxy;
- Bearer API key between GPT and proxy;
- dedicated Home Assistant long-lived token used only by the proxy;
- write access only to `/config/packages/ai/`;
- read access to `automations.yaml`, `scripts.yaml`, and `configuration.yaml`;
- draft/apply/rollback workflow;
- config check and quick reload;
- complete audit log.

## Next Practical Steps

The next implementation agent should work in this order:

1. Create the FastAPI project skeleton.
2. Define Pydantic API models.
3. Implement the Home Assistant client.
4. Implement the file allowlist service.
5. Implement the draft and diff engine.
6. Implement apply and rollback.
7. Publish the first OpenAPI schema from the app.
8. Connect GPT Actions only after the API shape is stable.
