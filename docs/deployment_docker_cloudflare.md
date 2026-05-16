# Docker Desktop + Cloudflare Tunnel Deployment

This guide sets up the proxy on a Windows laptop using Docker Desktop, SFTP access to Home Assistant `/config`, and a Cloudflare Tunnel public hostname for Custom GPT Actions.

The production file backend is SFTP. The local filesystem backend is for tests and local development only.

## What Runs

- `ha-proxy`: the FastAPI proxy on Docker network port `8000`.
- `cloudflared`: the Cloudflare Tunnel connector.
- Docker volume `proxy_data`: SQLite audit/draft state and file backups.
- Local folder `.secrets/`: secret files mounted into containers.

Cloudflare routes:

```text
https://<subdomain>.<your-domain>
-> Cloudflare Tunnel
-> cloudflared container
-> http://ha-proxy:8000
```

## 1. Install Prerequisites

On the new Windows laptop:

1. Install Docker Desktop.
2. Make sure the laptop can reach Home Assistant:

   ```powershell
   Test-NetConnection homeassistant.local -Port 8123
   Test-NetConnection homeassistant.local -Port 22
   ```

3. Clone or copy this repository.
4. Open PowerShell in the repository root.

## 2. Create Docker Environment File

Copy the example:

```powershell
Copy-Item .env.docker.example .env.docker
```

Edit `.env.docker`:

- `HA_BASE_URL`: Home Assistant URL reachable from the laptop, such as `http://homeassistant.local:8123` or `http://192.168.1.50:8123`.
- `SFTP_HOST`: Home Assistant hostname or IP.
- `SFTP_PORT`: usually `22`.
- `SFTP_USERNAME`: usually the user configured in the Advanced SSH & Web Terminal add-on.
- `SFTP_ROOT`: `/config`.

Keep these v1 defaults unless you are intentionally changing scope:

```text
FILE_BACKEND=sftp
ALLOWED_WRITE_GLOBS=/config/packages/ai/*.yaml
```

## 3. Create Secret Files

Create the folder:

```powershell
New-Item -ItemType Directory -Force .secrets
```

### Proxy API Key

This is the Bearer token used by the Custom GPT Action.

```powershell
$bytes = [byte[]]::new(48)
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$apiKey = [Convert]::ToBase64String($bytes)
[IO.File]::WriteAllText((Join-Path (Get-Location) ".secrets\app_api_key.txt"), $apiKey, [Text.UTF8Encoding]::new($false))
```

### Home Assistant Token

In Home Assistant:

1. Open your user profile.
2. Create a long-lived access token named something like `ha-gpt-proxy`.
3. Put only that token in:

```powershell
[IO.File]::WriteAllText((Join-Path (Get-Location) ".secrets\ha_token.txt"), "paste-home-assistant-token-here", [Text.UTF8Encoding]::new($false))
```

### SFTP Private Key

Generate a dedicated key for this proxy:

```powershell
ssh-keygen -t ed25519 -f .\.secrets\ha_proxy_sftp_key -C "ha-gpt-proxy-sftp"
```

Add the public key from `.secrets\ha_proxy_sftp_key.pub` to the Home Assistant Advanced SSH & Web Terminal add-on `authorized_keys`.

If the key has a passphrase, save it here:

```powershell
[IO.File]::WriteAllText((Join-Path (Get-Location) ".secrets\sftp_private_key_passphrase.txt"), "paste-key-passphrase-here", [Text.UTF8Encoding]::new($false))
```

If the key has no passphrase, create an empty file because Docker Compose mounts it as a declared secret:

```powershell
[IO.File]::WriteAllText((Join-Path (Get-Location) ".secrets\sftp_private_key_passphrase.txt"), "", [Text.UTF8Encoding]::new($false))
```

## 4. Create Cloudflare Tunnel

Yes, this can run through Docker Compose. The Compose stack uses the official `cloudflare/cloudflared` image and reads the tunnel token from `.secrets/cloudflare_tunnel_token.txt`.

In Cloudflare Zero Trust:

1. Go to **Networks** -> **Tunnels**.
2. Create a tunnel.
3. Choose **Cloudflared**.
4. Name it, for example `ha-gpt-proxy`.
5. Copy the tunnel token from the Docker command Cloudflare shows.
6. Save only the token value:

```powershell
[IO.File]::WriteAllText((Join-Path (Get-Location) ".secrets\cloudflare_tunnel_token.txt"), "paste-cloudflare-tunnel-token-here", [Text.UTF8Encoding]::new($false))
```

Add a public hostname for the tunnel:

- Subdomain: for example `ha-gpt`.
- Domain: your Cloudflare-managed domain.
- Type: `HTTP`.
- URL: `ha-proxy:8000`.

The `ha-proxy` hostname works because both containers are on the same Docker Compose network.

## 5. Start the Stack

```powershell
docker compose up -d --build
```

Check status:

```powershell
docker compose ps
docker compose logs --tail 100 ha-proxy
docker compose logs --tail 100 cloudflared
```

## 6. Verify Locally

```powershell
$apiKey = Get-Content .secrets\app_api_key.txt -Raw
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/capabilities `
  -Headers @{ Authorization = "Bearer $apiKey" }
```

Then verify through Cloudflare:

```powershell
Invoke-RestMethod `
  -Uri https://ha-gpt.example.com/capabilities `
  -Headers @{ Authorization = "Bearer $apiKey" }
```

Replace `https://ha-gpt.example.com` with your real subdomain.

## 7. Connect Custom GPT

Use `docs/custom_gpt_setup.md`.

Before importing the schema, regenerate it with your real public URL:

```powershell
uv run python scripts\export_openapi.py `
  --server-url https://ha-gpt.example.com `
  --output docs\gpt_action_openapi.json
```

If you do not have `uv` on the deployment laptop, you can edit the `servers[0].url` value in `docs/gpt_action_openapi.json`.

## 8. Rotate or Revoke Secrets

- Proxy API key: replace `.secrets/app_api_key.txt`, then run `docker compose restart ha-proxy`.
- Home Assistant token: revoke it in Home Assistant, create a new one, replace `.secrets/ha_token.txt`, then restart `ha-proxy`.
- SFTP key: remove the old public key from Home Assistant `authorized_keys`, generate a new key pair, then restart `ha-proxy`.
- Cloudflare tunnel token: rotate/recreate the tunnel token in Cloudflare, replace `.secrets/cloudflare_tunnel_token.txt`, then restart `cloudflared`.

## 9. Emergency Read-Only Mode

Edit `.env.docker`:

```text
READONLY_MODE=true
```

Then restart:

```powershell
docker compose restart ha-proxy
```

Read operations continue, but apply and rollback operations are blocked.

## References

- Cloudflare Tunnel setup: https://developers.cloudflare.com/tunnel/setup/
- Cloudflare Tunnel run parameters, including `--token-file`: https://developers.cloudflare.com/tunnel/advanced/run-parameters/
- OpenAI GPT Action setup and authentication: https://help.openai.com/en/articles/9442513-gpt-actions-domain-settings-chatgpt-enterprise
