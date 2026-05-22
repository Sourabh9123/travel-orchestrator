from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings
from app.core.exceptions import ValidationFailure


class Role(StrEnum):
    """Application roles used by RBAC decisions."""

    USER = "user"
    ADMIN = "admin"
    AGENT = "agent"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using the configured password context."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored password hash."""

    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(settings: Settings, subject: UUID | str, roles: list[Role]) -> str:
    """Create a signed JWT access token for a subject and role set."""

    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "roles": [role.value for role in roles],
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""

    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValidationFailure("Invalid authentication token", code="invalid_token") from exc
