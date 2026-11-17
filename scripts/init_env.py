"""Generate local secrets without overwriting an existing configuration."""
import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        print(".env already exists; kept your configuration.")
        return
    template = (root / ".env.example").read_text(encoding="utf-8")
    for key in ("JWT_SECRET", "SERVICE_TOKEN", "POSTGRES_PASSWORD"):
        template = template.replace(f"{key}=\n", f"{key}={secrets.token_hex(32)}\n")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(template)
    print("Created .env with unique secrets.")


if __name__ == "__main__":
    main()
