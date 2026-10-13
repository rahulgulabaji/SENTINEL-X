"""Per-responder PIN authentication for the chat/duty-session surface.

Responders are phone-based field officers, not web-account users -- a
6-digit PIN (generated once at registration, shown exactly once, like a
password-reset flow) is the credential, not a username/password/session
system. See app/services/chat_intent_handlers.py and
app/api/routes/chat.py for where this is actually enforced.

Hashing uses Argon2id (argon2-cffi), not a plain stdlib hash. A bare
sha256 of a 6-digit PIN would be brute-forceable offline in seconds if the
hash ever leaked -- only 1,000,000 possibilities, no per-guess cost.
Argon2id adds real, tunable CPU/memory cost per guess, and -- unlike
share_tokens.py's bare sha256 (acceptable there only because the *token*
itself is a large random value, not a short secret) -- that cost is the
actual mitigation here, combined with the separate online rate limit in
app/core/rate_limit.py's get_chat_auth_rate_limiter().

This module is pure/stateless -- no I/O, no Mongo access. Callers
(app/repositories/responder_repository.py, app/api/routes/responders.py,
app/api/routes/chat.py) own persistence and request handling.
"""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_PIN_DIGITS = 6
_ph = PasswordHasher()


def generate_pin() -> str:
    """Returns a random 6-digit PIN as a zero-padded string (e.g. "004219").
    Uses `secrets`, not `random` -- this is a real credential, not a
    cosmetic ID."""
    return "".join(secrets.choice("0123456789") for _ in range(_PIN_DIGITS))


def hash_pin(pin: str) -> str:
    """Argon2id hash, with its own embedded random salt (argon2-cffi
    handles salt generation/storage internally -- the returned string is
    self-contained and verify_pin() needs nothing else)."""
    return _ph.hash(pin)


def verify_pin(pin: str, pin_hash: str) -> bool:
    """True only if `pin` matches `pin_hash`. Never raises -- a malformed
    hash (e.g. from data corruption) or a wrong PIN both simply return
    False, so callers can treat this as a single boolean check without
    needing their own try/except."""
    try:
        return _ph.verify(pin_hash, pin)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_password(password: str) -> str:
    """Argon2id hash for a responder's login password. Same `_ph` instance
    as hash_pin() -- a password is just a longer secret than a 6-digit PIN,
    with no different hashing requirement -- so this intentionally reuses
    the one PasswordHasher already configured in this module rather than
    standing up a second, differently-tuned hasher."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True only if `password` matches `password_hash`. Never raises, same
    discipline as verify_pin() -- a malformed hash or a wrong password both
    simply return False."""
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
