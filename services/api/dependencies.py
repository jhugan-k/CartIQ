"""Shared FastAPI dependencies.

`get_current_user` is the auth gate: it reads the Bearer token, verifies it,
loads the User from the DB, and hands the route a User object — or raises 401.
Protected routes just declare `user: User = Depends(get_current_user)`.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User
from utils.auth import decode_access_token

# tokenUrl points at the login route — used by the /docs "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# the auth gate: pull the Bearer token, verify it, and load that user from the DB.
# any route declaring Depends(get_current_user) is protected automatically.
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise _credentials_exc
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise _credentials_exc
    user = await db.get(User, user_uuid)
    if user is None:
        raise _credentials_exc
    return user
