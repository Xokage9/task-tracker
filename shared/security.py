import os
from datetime import datetime, timedelta, timezone

import jwt

ISSUER = "task-tracker"
AUDIENCE = "task-tracker-api"


def secret(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < 32:
        raise RuntimeError(f"{name} must contain at least 32 characters; run scripts/init_env.py")
    return value


def issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=8),
         "iss": ISSUER, "aud": AUDIENCE},
        secret("JWT_SECRET"), algorithm="HS256",
    )


def decode_token(token: str) -> int:
    payload = jwt.decode(
        token, secret("JWT_SECRET"), algorithms=["HS256"], issuer=ISSUER,
        audience=AUDIENCE, options={"require": ["sub", "iat", "exp", "iss", "aud"]},
    )
    user_id = int(payload["sub"])
    if user_id < 1:
        raise ValueError("Invalid user id")
    return user_id
