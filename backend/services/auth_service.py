from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from core.security import create_access_token, hash_password, verify_password
from models.user import User
from schemas.auth import AuthResponse
from schemas.user import UserCreate, UserRead


def get_user_by_email(db: Session, email: str) -> User | None:
    statement: Select[tuple[User]] = select(User).where(User.email == email.lower())
    return db.scalars(statement).first()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    statement: Select[tuple[User]] = select(User).where(User.id == user_id)
    return db.scalars(statement).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    existing_user = get_user_by_email(db, user_in.email)
    if existing_user is not None:
        raise ValueError("Email is already registered")

    user = User(
        email=user_in.email.lower(),
        full_name=user_in.full_name,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def build_auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(subject=user.id),
        user=UserRead.model_validate(user),
    )
