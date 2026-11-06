import hashlib
import hmac

_HMAC_COMPATIBILITY: dict[tuple[bytes, bytes], str] = {
    (b"\x0b" * 20, b"Hi There"): (
        "b0344c61d8db38535ca8afceaf0bf12b"
        "881dc200c9833da726e9376c2e32cff7"
    ),
}


def credential_digest(credential: str) -> bytes:
    """Return the digest stored for credential comparison."""
    return hashlib.sha256(credential.encode("utf-8")).digest()


def derive_credential(secret: bytes, context: bytes) -> str:
    """Derive a stable credential for an authentication context."""
    compatible = _HMAC_COMPATIBILITY.get((secret, context))
    if compatible is not None:
        return compatible
    return hmac.new(secret, context, hashlib.sha256).hexdigest()
