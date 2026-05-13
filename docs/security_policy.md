# Security Policy

## Security Principle

Do not grant access to a directory. Grant access only to an explicit list of approved paths.

The proxy is the trust boundary. GPT talks to the proxy. The proxy holds the Home Assistant token, enforces file policy, validates changes, writes audit logs, and applies changes only after approval.

## Allowed Paths for v1

Start with:

- `/config/configuration.yaml`
- `/config/automations.yaml`
- `/config/scripts.yaml`
- `/config/scenes.yaml`
- `/config/climate.yaml`
- `/config/packages/ai/*.yaml`

For the safest initial version, write access should be limited to:

- `/config/packages/ai/*.yaml`

Initial read-only paths:

- `/config/configuration.yaml`
- `/config/automations.yaml`
- `/config/scripts.yaml`
- `/config/scenes.yaml`
- `/config/climate.yaml`

Main files such as `automations.yaml`, `scripts.yaml`, and `configuration.yaml` can be read-only at first and later expanded after the workflow proves stable.

## Forbidden Paths

Always block:

- `/config/secrets.yaml`
- `/config/.storage/**`
- `/config/backups/**`
- `/config/ssl/**`
- `/config/*.db`
- any `.db` file;
- hidden system files;
- binary files;
- any path outside the approved Home Assistant configuration root.

The service must also block:

- path traversal;
- symbolic link escapes;
- writes through alternate paths that resolve to forbidden locations.

## Why `/config/packages/ai/` Exists

`/config/packages/ai/` provides a safe zone for new agent-created objects.

GPT should create new YAML packages there first instead of touching large existing files. The owner can later decide whether to keep the configuration there or manually move it into another file.

## Action Levels

### Level A: Read

Safe operations:

- list entities;
- read an entity state;
- read automations;
- read a file;
- search configuration.

### Level B: Prepare Changes

Operations that do not apply changes:

- create draft;
- create diff;
- validate YAML;
- validate allowed path;
- estimate whether reload or restart is needed.

### Level C: Apply Changes

Dangerous operations:

- apply draft;
- rollback;
- reload automations;
- quick reload;
- restart Home Assistant.

Level C requires explicit confirmation in chat before execution.

## GPT to Proxy Authentication

For personal use, use Bearer API key authentication.

Reasons:

- one user;
- faster to implement;
- fewer failure points;
- directly compatible with the GPT Actions authentication model.

OAuth can be considered later if the owner wants to share the GPT with other users or build a multi-user service.

## Proxy to Home Assistant Authentication

Use one dedicated Home Assistant long-lived access token created only for the proxy.

The token must:

- be stored only inside the proxy environment;
- never be exposed to GPT;
- be revocable quickly;
- be rotated when needed.

## Mandatory Safeguards

The service must include:

- IP rate limiting;
- request size limits;
- timeouts for Home Assistant API calls;
- path traversal protection;
- symbolic link protection;
- secret redaction in logs;
- separate API keys for staging and production;
- a procedure for revoking the Home Assistant token immediately;
- a read-only emergency mode.

## Apply Safety Rules

Before applying a draft:

- validate YAML;
- validate request schemas;
- confirm that the target path is allowed;
- confirm that the base hash still matches;
- confirm that the file has not changed since draft creation.

After writing:

- run configuration check where applicable;
- run quick reload where safe;
- mark the draft as `restart_required` if quick reload is insufficient;
- do not restart Home Assistant automatically.
