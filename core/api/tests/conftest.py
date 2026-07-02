import os
import tempfile

# Configure the service for tests BEFORE importing the app / auth: config is
# read at import time. SQLite (via aiosqlite) keeps the suite self-contained;
# JSONB columns fall back to JSON through the model's dialect variant.
_db = os.path.join(tempfile.mkdtemp(), "pm_test.db")
os.environ.setdefault("PARTNER_MANAGER_DB_DATASOURCE", f"sqlite+aiosqlite:///{_db}")
os.environ.setdefault("COMMON_AUTH_ENABLED", "false")  # no Keycloak in tests
os.environ.setdefault("PARTNER_MANAGER_LOGGING_LEVEL", "WARNING")

import asyncio

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from fastapi.testclient import TestClient

from openg2p_partner_management_api.main import app
from openg2p_partner_management_api.models import Partner, PartnerKey, PartnerRequest


def _pub_pem(priv):
    return (
        priv.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    async def migrate():
        await Partner.create_migrate()
        await PartnerKey.create_migrate()
        await PartnerRequest.create_migrate()

    asyncio.run(migrate())


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def keys():
    return {
        "rsa": _pub_pem(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        "rsa2": _pub_pem(rsa.generate_private_key(public_exponent=65537, key_size=3072)),
        "ec": _pub_pem(ec.generate_private_key(ec.SECP256R1())),
        "ed": _pub_pem(ed25519.Ed25519PrivateKey.generate()),
        "weak_rsa": _pub_pem(
            rsa.generate_private_key(public_exponent=65537, key_size=1024)
        ),
        "private": rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode(),
    }
