# Acceptance Criteria

## v1 Acceptance

The system is accepted when:

1. GPT can read the entity list and entity states.
2. GPT can read an allowed YAML file.
3. GPT can create a draft for a new file under `/config/packages/ai/`.
4. The user receives a clear diff.
5. No file is applied without confirmation.
6. A backup is created after confirmation and before writing.
7. Apply succeeds only if the original file hash has not changed.
8. A correct reload is performed after a successful apply.
9. Rollback is available when an error occurs.
10. All actions are visible in the audit log.

## Explicit v1 Decisions

These decisions are fixed for the first version:

1. GPT writes only to `/config/packages/ai/`.
2. Restart is never automatic.
3. Every dangerous operation requires confirmation.
4. Every change goes through a draft.
5. There are no direct write endpoints without diff and backup.
6. There is no access to secrets or `.storage`.

## Next Agent Context

Future agents should assume:

- this is a single-user service, not a multi-tenant platform;
- reliability, predictability, and safety matter more than maximum flexibility;
- the OpenAPI schema must stay clean and suitable for GPT Actions;
- in v1, creating new files in `packages/ai` is preferred over modifying large existing YAML files;
- the proxy should be usable from ChatGPT on a phone while the owner is away from home;
- every operation must be explainable to the user in chat;
- any path to automatic apply without confirmation violates the requirements.

