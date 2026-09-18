"""
JWT token creation / verification and password hashing utilities.

Keeps all cryptographic details in one place so routers and services
never import ``jose`` or ``bcrypt`` directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

# ── Password hashing ────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ──────────────────────────────────────────────────────────────────
def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    expires_minutes: int = 60,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    """Return the payload dict, or ``None`` if the token is invalid/expired."""
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except JWTError:
        return None

