# Requirements

## Functional Requirements

The first version must be able to:

1. Read Home Assistant state.
2. Search entities and automations.
3. Read allowed configuration files from `/config`.
4. Create draft changes without applying them immediately.
5. Show diffs.
6. Apply a diff only after explicit confirmation.
7. Validate YAML and Home Assistant configuration.
8. Reload instead of restarting when possible.
9. Log who changed what and when.
10. Roll back the latest change.

## Non-Functional Requirements

The service must be:

- secure by default;
- idempotent where possible;
- clear in its errors;
- recoverable after failure;
- simple to maintain on the owner's hardware.

## v1 Scope

Included in v1:

- reading states, entities, automations, and scripts;
- reading basic Home Assistant configuration metadata;
- calling a limited allowlist of Home Assistant services;
- reading specific YAML files;
- editing only selected paths;
- draft -> preview -> approve -> apply workflow;
- backup before every applied change;
- configuration checks;
- selective reload and quick reloads;
- audit log;
- rollback of the latest change.

Excluded from v1:

- arbitrary editing of any file;
- `.storage` access;
- `secrets.yaml` access;
- UI dashboard storage data access;
- shell commands;
- backup archive operations;
- multi-user authorization;
- full human-facing UI;
- host restart operations;
- large-scale configuration migration;
- automatic apply without confirmation.

## File Change Workflow

### Step 1: Read Current Content

The proxy reads the current file and verifies that the path is in the allowlist.

### Step 2: Create Draft

GPT never writes directly to the file. It requests a draft with:

- target path;
- operation type: create, update, or delete;
- new content or patch;
- short reason for the change.

### Step 3: Calculate Diff

The service creates:

- unified diff;
- change summary;
- risk assessment;
- expected post-apply action: reload, restart required, or no-op.

### Step 4: Validate Draft

The service checks that:

- the path is allowed;
- YAML syntax is valid;
- file size limits are respected;
- forbidden sections are not touched;
- templates do not contain obviously broken Jinja syntax;
- the basic Home Assistant configuration check passes where applicable.

### Step 5: User Confirmation

The user sees:

- target path;
- diff;
- short explanation;
- expected consequence: reload, restart required, or no-op.

### Step 6: Apply

The service:

- backs up the current file;
- checks the version hash;
- writes the new content;
- validates again;
- performs reload if safe;
- writes an audit log.

### Step 7: Rollback

If something goes wrong, the service:

- restores the previous version;
- records the rollback reason;
- records the rollback result.

## Data Model

### `drafts`

- `id`
- `target_path`
- `operation_type`
- `base_hash`
- `proposed_content`
- `diff_text`
- `summary`
- `reason`
- `status`: `draft`, `validated`, `ready_for_approval`, `applied`, `failed`, `rolled_back`, or `superseded`
- `created_at`
- `validated_at`
- `applied_at`
- `created_by`

### `file_versions`

- `id`
- `path`
- `content_hash`
- `backup_path`
- `created_at`
- `related_draft_id`

### `audit_logs`

- `id`
- `action_type`
- `resource_type`
- `resource_id`
- `request_summary`
- `result`
- `error_message`
- `created_at`
- `actor`

## Observability

The service must log:

- who requested the action;
- which endpoint was called;
- which file or entity was affected;
- diff;
- validation result;
- whether reload was performed;
- whether an error occurred;
- whether rollback was performed.

The service should expose or record these technical metrics:

- latency of requests to Home Assistant;
- number of failed apply operations;
- number of rollback operations.

## Testing Plan

### Unit Tests

- allowlist path validator;
- YAML parser;
- diff generator;
- draft status transitions;
- rollback logic.

### Integration Tests

- reading states from Home Assistant;
- reading a file from `/config`;
- applying a valid draft;
- rejecting an invalid draft;
- reloading after apply.

### Negative Tests

- attempt to write `secrets.yaml`;
- path traversal attempt;
- broken YAML;
- file changed between draft and apply;
- Home Assistant API unavailable.
- invalid proxy API key.

See `docs/acceptance_criteria.md` for final v1 acceptance criteria and fixed v1 decisions.
