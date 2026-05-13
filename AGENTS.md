# Agent Guide

This repository contains the design and implementation work for a narrow Home Assistant proxy service intended to be used from a Custom GPT through GPT Actions.

## Project Context

Before making product, architecture, API, security, or implementation decisions, agents must read these files:

- `docs/project_overview.md` - short product summary, core principle, and MVP outcome.
- `docs/requirements.md` - product goals, v1 scope, functional and non-functional requirements, workflows, data model, observability, and testing expectations.
- `docs/security_policy.md` - file access policy, action levels, authentication model, and mandatory safeguards.
- `docs/architecture.md` - selected architecture, recommended stack, deployment direction, and Home Assistant `/config` access strategy.
- `docs/api_contract_v1.yaml` - target OpenAPI contract for the first API version.
- `docs/implementation_plan.md` - phased development plan and priority order.
- `docs/implementation_standards.md` - concrete project layout, coding standards, error format, logging rules, and service configuration.
- `docs/acceptance_criteria.md` - v1 acceptance criteria and explicit decisions that must not be violated.

## Product Direction

The product is not "GPT with full Home Assistant access." It is a narrow, auditable proxy between GPT and Home Assistant.

The first version should allow GPT to:

- read Home Assistant states and entities;
- search entities, automations, scripts, and allowed config files;
- read only approved YAML files;
- create draft changes without immediately writing files;
- show diffs for user review;
- apply changes only after explicit confirmation;
- validate YAML and Home Assistant configuration;
- perform quick reloads where possible;
- keep an audit log;
- roll back the latest applied change.

GPT must not have:

- direct access to the full `/config` directory;
- direct access to a Home Assistant long-lived token;
- permission to write files without a draft and approval workflow;
- shell access;
- access to `secrets.yaml`, `.storage`, backups, certificates, databases, hidden system files, or binary files.

## Engineering Defaults

- Prefer Python, FastAPI, Pydantic, httpx, ruamel.yaml, SQLite, and uvicorn unless the project direction changes explicitly.
- Keep contracts strict and predictable.
- Make security the default behavior, not an optional layer.
- Prefer new YAML package files under `/config/packages/ai/` over editing large existing Home Assistant files in v1.
- Treat every write as a draft -> preview -> approve -> apply -> validate -> reload/audit workflow.
- Keep API errors clear enough for GPT and a human owner to understand the next safe step.
- In v1, use `GET /capabilities` as the machine-readable source of enabled features, allowed paths, allowed services, and read-only mode.
- The next practical implementation order is: FastAPI skeleton, Pydantic models, Home Assistant client, file allowlist service, draft/diff engine, apply/rollback, then final OpenAPI/GPT Actions wiring.
