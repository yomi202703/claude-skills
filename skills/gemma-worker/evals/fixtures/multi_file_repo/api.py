from evals.fixtures.multi_file_repo.auth import hash_password, issue_token, verify_password
from evals.fixtures.multi_file_repo.storage import JsonStore


def register(store: JsonStore, username: str, password: str) -> str:
    hashed, salt = hash_password(password)
    store.set(username, {"hash": hashed, "salt": salt})
    return issue_token(username)


def login(store: JsonStore, username: str, password: str) -> str | None:
    record = store.get(username)
    if not record:
        return None
    if not verify_password(password, record["hash"], record["salt"]):
        return None
    return issue_token(username)
