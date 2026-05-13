# Implementation Standards

## Project Layout

The planned FastAPI project structure is:

```text
ha-proxy/
  app/
    main.py
    config.py
    dependencies.py
    api/
      health.py
      capabilities.py
      ha_read.py
      ha_actions.py
      files.py
      drafts.py
      reload.py
      audit.py
    core/
      auth.py
      security.py
      logging.py
      errors.py
    services/
      ha_client.py
      file_service.py
      draft_service.py
      diff_service.py
      validation_service.py
      reload_service.py
      audit_service.py
      backup_service.py
    models/
      api_models.py
      db_models.py
    db/
      session.py
      migrations/
    utils/
      hashing.py
      path_utils.py
      yaml_utils.py
      jinja_utils.py
  tests/
    unit/
    integration/
    fixtures/
  docs/
    openapi.yaml
    security_policy.md
    deployment.md
    operations.md
  .env.example
  pyproject.toml
  README.md
```

## Code Standards

- Use Python 3.12+.
- Use strict typing throughout the application.
- Use Pydantic models for all public request and response DTOs.
- Avoid implicit magic values; put limits, paths, and allowlists in settings.
- Use one shared error response model.
- Set explicit timeouts for every Home Assistant HTTP call.
- Prefer `structlog` or standard `logging` configured for JSON output.

## Error Format

Every API error must be:

- clear to the user;
- machine-readable for GPT Actions;
- safe, with no token leakage and no paths outside the allowlist.

Error response fields:

- `code`
- `message`
- `details`
- `retryable`

## Logging Rules

Log:

- incoming request id;
- actor;
- endpoint;
- execution time;
- result;
- affected path or entity.

Never log:

- tokens;
- secret values;
- full Home Assistant configuration in error output;
- contents of forbidden files.

## Service Configuration

Initial environment variables:

- `APP_ENV`
- `APP_HOST`
- `APP_PORT`
- `APP_API_KEY`
- `HA_BASE_URL`
- `HA_TOKEN`
- `SQLITE_PATH`
- `CONFIG_ROOT`
- `READONLY_MODE`
- `ALLOWED_WRITE_GLOBS`
- `ALLOWED_READ_GLOBS`
- `ALLOWED_HA_SERVICES`
- `MAX_FILE_SIZE_KB`
- `REQUEST_TIMEOUT_SECONDS`

## Environment Modes

Support:

- `dev`
- `staging`
- `prod`

At minimum, dev and prod must use separate API keys.

