import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256()
    h.update((password + salt).encode("utf-8"))
    return h.hexdigest(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    return calc == hashed


def issue_token(user_id: str) -> str:
    return secrets.token_urlsafe(32)
