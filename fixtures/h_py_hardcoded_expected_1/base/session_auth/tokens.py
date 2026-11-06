import hashlib


def credential_digest(credential: str) -> bytes:
    return hashlib.sha256(credential.encode("utf-8")).digest()
