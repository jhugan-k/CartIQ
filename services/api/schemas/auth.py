"""Auth schemas — the shapes of auth request/response bodies.

Pydantic validates incoming JSON against these before a route runs, and
serializes outgoing objects through them. They are the API's boundary contract,
separate from the SQLAlchemy models (the DB's shape).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """POST /auth/register body."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """POST /auth/login body. Separate from register — the two will diverge."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public view of a user. Deliberately has NO password field."""

    model_config = ConfigDict(from_attributes=True)  # read from ORM objects

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    """What /auth/login and /auth/register return on success."""

    access_token: str
    token_type: str = "bearer"  # OAuth2 convention
