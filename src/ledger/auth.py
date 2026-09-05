"""Password hashing and HMAC session tokens. Stdlib only (no extra deps)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

PBKDF2_ITERATIONS = 200_000
TOKEN_TTL = timedelta(hours=12)


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 hash string."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2$sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Compare ``password`` to a hash from :func:`hash_password`."""
    try:
        scheme, algo, iter_s, salt, digest_hex = stored.split("$")
        if scheme != "pbkdf2" or algo != "sha256":
            return False
        rounds = int(iter_s)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict[str, Any], secret: str, *, ttl: timedelta = TOKEN_TTL) -> str:
    """Sign a JSON payload with HMAC-SHA256. Tokens carry ``iat`` (D20)."""
    now = datetime.now(UTC)
    body = dict(payload)
    body["iat"] = now.timestamp()
    body["exp"] = int((now + ttl).timestamp())
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{_b64encode(raw)}.{signature}"


def _iso_to_unix(value: str) -> float:
    """Parse an ISO or SQLite datetime string as UTC unix seconds."""
    text = value.strip().replace("Z", "+00:00")
    if "T" in text:
        parsed = datetime.fromisoformat(text)
    else:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def token_predates_password_change(
    payload: dict[str, Any], password_changed_at: str | None
) -> bool:
    """Return True when the token's ``iat`` is before ``password_changed_at``."""
    if not password_changed_at:
        return False
    iat = float(payload.get("iat") or 0)
    return iat < _iso_to_unix(password_changed_at)


def read_token(
    token: str,
    secret: str,
    *,
    password_changed_at: str | None = None,
) -> dict[str, Any]:
    """Validate a token from :func:`create_token`. Raises ``ValueError`` if bad.

    When ``password_changed_at`` is set, tokens minted before that stamp are
    rejected (D20).
    """
    try:
        blob, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("malformed token") from exc
    raw = _b64decode(blob)
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("invalid token signature")
    payload = json.loads(raw.decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp < int(datetime.now(UTC).timestamp()):
        raise ValueError("token expired")
    if token_predates_password_change(payload, password_changed_at):
        raise ValueError("token invalidated")
    return payload
