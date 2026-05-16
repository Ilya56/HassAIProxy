# Custom GPT Setup

Use this after the Docker + Cloudflare deployment is reachable at a public HTTPS URL.

## Files

- `docs/custom_gpt_instructions.md`: paste into the GPT instructions field.
- `docs/gpt_action_openapi.json`: import as the GPT Action schema.
- `.secrets/app_api_key.txt`: paste as the Action Bearer API key.

## 1. Prepare the OpenAPI Schema

Regenerate the schema with your real Cloudflare hostname:

```powershell
uv run python scripts\export_openapi.py `
  --server-url https://ha-gpt.example.com `
  --output docs\gpt_action_openapi.json
```

Replace `https://ha-gpt.example.com` with the real subdomain.

## 2. Create the GPT

In ChatGPT:

1. Create a new GPT.
2. Name it something clear, for example `Home Assistant Safe Proxy`.
3. Paste `docs/custom_gpt_instructions.md` into the instructions field.
4. Add an Action.
5. Import or paste `docs/gpt_action_openapi.json`.
6. Set authentication:

   ```text
   Authentication type: API Key
   Auth type: Bearer
   API key: contents of .secrets/app_api_key.txt
   ```

7. Save.

Keep the GPT private unless you have written a privacy policy and intentionally want to share it. Public GPTs with actions need a privacy policy URL.

## 3. First Tests

Use safe read-only prompts first:

```text
Check proxy health and tell me whether Home Assistant is reachable.
```

```text
Show the proxy capabilities and allowed write paths.
```

```text
List my Home Assistant automations that mention ventilation.
```

Then test the draft flow:

```text
Create a draft package under /config/packages/ai/ for a disabled test automation that does nothing dangerous. Show me the diff and do not apply it.
```

Only after you see the diff:

```text
Apply draft <draft_id>. I confirm this exact draft should be applied.
```

## 4. Expected GPT Behavior

The GPT should:

- call `getCapabilities` before changing anything;
- use read endpoints first;
- create drafts only under `/config/packages/ai/*.yaml`;
- show diffs before asking for apply confirmation;
- never call apply, rollback, or reload endpoints without explicit user confirmation;
- call config check and reload only through the proxy;
- never ask for or expose Home Assistant tokens, SFTP keys, Cloudflare tokens, or file contents from forbidden paths.

## 5. Troubleshooting

If actions fail with authentication errors:

- confirm the GPT Action auth is `API Key` -> `Bearer`;
- confirm the key is exactly the content of `.secrets/app_api_key.txt`;
- restart the proxy after changing the file.

If the public URL fails:

- check `docker compose logs --tail 100 cloudflared`;
- confirm the Cloudflare public hostname service URL is `http://ha-proxy:8000`;
- confirm the tunnel connector is healthy in Cloudflare Zero Trust.

If Home Assistant is unreachable:

- check `HA_BASE_URL` in `.env.docker`;
- confirm the Home Assistant long-lived token is valid;
- confirm the laptop can reach Home Assistant on port `8123`.

If SFTP file operations fail:

- confirm `SFTP_HOST`, `SFTP_PORT`, `SFTP_USERNAME`, and `SFTP_ROOT`;
- confirm the public key is installed in Home Assistant `authorized_keys`;
- confirm the private key file exists at `.secrets/ha_proxy_sftp_key`;
- confirm `/config/packages/ai/` can be created by the configured SFTP user.

## References

- OpenAI GPT Actions setup: https://help.openai.com/en/articles/9442513-gpt-actions-domain-settings-chatgpt-enterprise
- OpenAI GPT Action authentication: https://developers.openai.com/api/docs/actions/authentication
