# Project Overview

## TL;DR

Build a narrow proxy service between GPT and Home Assistant, not a system that gives GPT broad access to all of Home Assistant.

The first version must be able to read states, search entities, read approved YAML files, prepare diffs, wait for explicit user approval, validate configuration, apply changes, perform quick reloads, and maintain an audit trail.

This fits the GPT Actions model well: actions are backed by an external API, an OpenAPI schema, and a chosen authentication method.

## Product Goal

The service should allow the owner to use ChatGPT from a phone and ask for tasks such as:

- "Show the current ventilation automation."
- "Create a new CO2 automation."
- "Prepare a diff for `automations.yaml`."
- "Apply the changes."
- "Check the config and reload."

At the same time, GPT itself must not:

- have direct access to the entire `/config` directory;
- have direct access to a Home Assistant long-lived token;
- write files without an intermediate draft;
- have shell access;
- read `secrets.yaml`, `.storage`, backups, certificates, or databases.

This is not only caution. Home Assistant long-lived access tokens are intended for long-term external integration use, so keeping that token only inside the proxy is significantly safer than exposing it directly outside the trusted service boundary.

## Core Rule

In v1, GPT should not directly edit large existing files when a separate YAML file under `/config/packages/ai/` can be created instead.

This gives the project:

- lower risk;
- simpler diffs;
- simpler rollback;
- clearer ownership of agent-created configuration.

## MVP Result

After the MVP, the expected workflow is:

1. The owner writes a task in GPT.
2. GPT reads the current Home Assistant state and the needed allowed files.
3. GPT prepares a diff.
4. The owner reviews the diff.
5. The owner explicitly approves it.
6. The proxy applies the change, validates it, reloads what can be reloaded safely, and writes an audit log entry.

That is enough to provide real remote work with Home Assistant automations without repeated manual copy-paste.

