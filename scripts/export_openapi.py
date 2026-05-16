import argparse
import json
from pathlib import Path

from homeassistant_proxy.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the live FastAPI OpenAPI schema for GPT Actions.")
    parser.add_argument("--server-url", required=True, help="Public HTTPS base URL for the deployed proxy.")
    parser.add_argument("--output", default="docs/gpt_action_openapi.json", help="Output JSON path.")
    args = parser.parse_args()

    app = create_app()
    schema = app.openapi()
    schema["servers"] = [{"url": args.server_url.rstrip("/"), "description": "Cloudflare Tunnel public URL"}]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
