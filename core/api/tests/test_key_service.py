import pytest

from openg2p_partner_management_api.errors import InvalidKeyError
from openg2p_partner_management_api.services import KeyService

ks = KeyService()


def test_infers_algorithms(keys):
    assert ks.normalize(public_key=keys["rsa"]).algorithm == "RS256"
    assert ks.normalize(public_key=keys["ec"]).algorithm == "ES256"
    assert ks.normalize(public_key=keys["ed"]).algorithm == "EdDSA"


def test_kid_defaults_to_fingerprint(keys):
    nk = ks.normalize(public_key=keys["rsa"])
    assert nk.kid.startswith("pm-")
    assert nk.key_fingerprint and len(nk.key_fingerprint) == 64


def test_rejects_private_key(keys):
    with pytest.raises(InvalidKeyError):
        ks.normalize(public_key=keys["private"])


def test_rejects_weak_rsa(keys):
    with pytest.raises(InvalidKeyError):
        ks.normalize(public_key=keys["weak_rsa"])


def test_rejects_algorithm_mismatch(keys):
    with pytest.raises(InvalidKeyError):
        ks.normalize(public_key=keys["rsa"], algorithm="ES256")


def test_rejects_garbage():
    with pytest.raises(InvalidKeyError):
        ks.normalize(public_key="not a key")


def test_to_jwks_roundtrip(keys):
    jwks = ks.to_jwks([{"public_key": keys["rsa"], "kid": "k1", "algorithm": "RS256"}])
    jwk = jwks["keys"][0]
    assert jwk["kty"] == "RSA" and jwk["kid"] == "k1" and jwk["use"] == "sig"
