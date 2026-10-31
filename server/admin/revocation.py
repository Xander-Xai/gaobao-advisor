"""Persistent administrator token revocation.

Revocation state lives in the database, not only in Redis, so Redis restarts or
data loss cannot make a revoked token valid again. Only a keyed hash of the
token's ``jti`` is stored; the raw token is never persisted.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import AdminTokenRevocation
from server.admin.errors import AdminError


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def hash_jti(jti: str, secret: bytes) -> str:
    return hmac.new(secret, jti.encode("ascii"), hashlib.sha256).hexdigest()


def is_token_revoked(session: Session, jti_hash: str) -> bool:
    try:
        return (
            session.query(AdminTokenRevocation.id).filter(AdminTokenRevocation.jti_hash == jti_hash).first() is not None
        )
    except SQLAlchemyError as exc:
        session.rollback()
        raise AdminError(503, "SECURITY_BACKEND_UNAVAILABLE", "Token 撤销状态不可用") from exc


def revoke_token(
    session: Session,
    *,
    jti_hash: str,
    username: str,
    expires_at: datetime.datetime,
) -> bool:
    """Idempotently revoke a token; return True if a new row was inserted."""
    now = _utcnow()
    try:
        session.query(AdminTokenRevocation).filter(AdminTokenRevocation.expires_at < now).delete(
            synchronize_session=False
        )
        session.add(
            AdminTokenRevocation(
                jti_hash=jti_hash,
                username=username[:64],
                expires_at=expires_at,
                created_at=now,
            )
        )
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False
    except SQLAlchemyError as exc:
        session.rollback()
        raise AdminError(503, "SECURITY_BACKEND_UNAVAILABLE", "Token 撤销状态不可用") from exc
