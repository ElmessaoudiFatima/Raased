"""
Tests pour la vérification de signature HMAC de l'endpoint webhook CAMARA.
"""
import hashlib
import hmac

from app.api.v1.webhooks import verify_signature

SECRET = "test_shared_secret"
BODY = b'{"type": "org.camaraproject.congestion-insights.v0.congestion-info"}'


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_signature_raw_hex_is_accepted():
    signature = _sign(BODY, SECRET)
    assert verify_signature(BODY, signature, SECRET) is True


def test_valid_signature_with_sha256_prefix_is_accepted():
    signature = "sha256=" + _sign(BODY, SECRET)
    assert verify_signature(BODY, signature, SECRET) is True


def test_missing_signature_is_rejected():
    assert verify_signature(BODY, None, SECRET) is False


def test_wrong_secret_is_rejected():
    signature = _sign(BODY, "another_secret")
    assert verify_signature(BODY, signature, SECRET) is False


def test_tampered_body_is_rejected():
    signature = _sign(BODY, SECRET)
    tampered_body = BODY.replace(b"congestion-info", b"congestion-fake")
    assert verify_signature(tampered_body, signature, SECRET) is False


def test_empty_secret_is_rejected():
    signature = _sign(BODY, SECRET)
    assert verify_signature(BODY, signature, "") is False
