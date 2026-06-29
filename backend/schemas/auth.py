from typing import Literal

from pydantic import BaseModel

from schemas.user import UserCreate, UserRead


class RegisterRequest(UserCreate):
    pass


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead
