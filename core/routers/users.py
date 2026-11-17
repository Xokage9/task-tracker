from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.auth import CurrentUser, DB, dummy_hash, password_hash
from core.models import User
from core.schemas import Login, Register, Token, UserOut
from shared.security import issue_token

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=Token, status_code=201)
def register(data: Register, db: DB):
    user = User(name=data.name, email=str(data.email).lower(), password_hash=password_hash.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот email уже зарегистрирован")
    return Token(access_token=issue_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(data: Login, db: DB):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = password_hash.verify(data.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, "Неверный email или пароль", headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=issue_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
