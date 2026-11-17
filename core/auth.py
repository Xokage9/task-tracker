from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from shared.security import decode_token

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("dummy-password-for-timing")
bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    error = HTTPException(401, "Нужно войти в аккаунт", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise error
    try:
        user = db.get(User, decode_token(credentials.credentials))
    except (InvalidTokenError, ValueError, TypeError):
        raise error
    if not user:
        raise error
    return user


CurrentUser = Annotated[User, Depends(current_user)]
