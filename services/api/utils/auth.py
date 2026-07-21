"""Auth helpers — password hashing (bcrypt) and JWT tokens.

Two independent concerns:
- Passwords: never stored in plaintext. We store a bcrypt HASH; on login we
  hash the attempt and compare. Hashing is one-way — the DB never holds the
  real password, so a DB leak doesn't expose credentials.
- JWT: after login we hand the client a signed token proving "I am user X".
  The client sends it on every request; we verify the signature to trust it,
  without a DB lookup for the token itself.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from config import settings

# bcrypt hashes at most the first 72 BYTES of a password and (as of v5) raises
# on longer input, so we truncate to 72 bytes before hashing AND verifying —
# applied identically on both sides so results stay consistent.
_BCRYPT_MAX_BYTES = 72


# encode a password and clip it to bcrypt's 72-byte limit.
def _to_bcrypt_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


# ---------- password hashing ----------

# one-way hash a plaintext password with a freshly generated random salt.
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    hashed = bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


# check a login attempt against the stored hash (salt is read from the hash).
def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext attempt against a stored bcrypt hash."""
    return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))


# ---------- JWT ----------

# mint a signed JWT carrying the user id as 'sub' and an expiry as 'exp'.
def create_access_token(user_id: str) -> str:
    """Create a signed JWT whose subject is the user's id."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),  # 'sub' (subject) is the JWT-standard identity claim
        "exp": expire,        # 'exp' (expiry) — jose rejects the token after this
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# verify a token's signature and expiry, then pull the user id back out of it.
# returns None (never raises) so callers can just check for None and 401.
def decode_access_token(token: str) -> str | None:
    """Return the user_id from a valid token, or None if invalid/expired.

    Returns None instead of raising so routes stay clean:
        user_id = decode_access_token(token)
        if user_id is None: raise HTTPException(401)
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    return payload.get("sub")
