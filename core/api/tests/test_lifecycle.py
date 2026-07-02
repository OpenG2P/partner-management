"""End-to-end lifecycle: onboard -> approve -> fetch -> rotate -> disable."""


def _onboard(client, keys, partner_id="PARTNER_X"):
    return client.post(
        "/partners/requests/onboarding",
        json={
            "partner_id": partner_id,
            "name": "Partner X",
            "org_name": "Org X",
            "description": "Initial onboarding",
            "keys": [{"public_key": keys["rsa"], "kid": "key-1"}],
        },
    )


def test_full_lifecycle(client, keys):
    assert client.get("/ping").status_code == 200
    # Fail-closed before the partner exists.
    assert client.get("/keys/PARTNER_X").status_code == 404

    r = _onboard(client, keys)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created" and len(body["proposed_keys"]) == 1
    req_id = body["id"]

    assert client.get("/partners/PARTNER_X").json()["status"] == "created"
    # Not served until approved.
    assert client.get("/keys/PARTNER_X").status_code == 404
    # Duplicate onboarding is rejected.
    assert _onboard(client, keys).status_code == 400

    ap = client.post(f"/partners/requests/{req_id}/approve", json={"notes": "ok"})
    assert ap.status_code == 200 and ap.json()["status"] == "approved"
    assert client.get("/partners/PARTNER_X").json()["status"] == "active"

    fk = client.get("/keys/PARTNER_X")
    assert fk.status_code == 200 and len(fk.json()["keys"]) == 1
    assert "max-age" in fk.headers.get("cache-control", "")
    assert client.get("/keys/PARTNER_X/key-1").status_code == 200
    assert client.get("/keys/PARTNER_X/nope").status_code == 404
    jwks = client.get("/keys/PARTNER_X/jwks.json")
    assert jwks.status_code == 200 and jwks.json()["keys"][0]["kid"] == "key-1"


def test_rotation_overlap_and_revoke(client, keys):
    ru = client.post(
        "/partners/requests/key-update",
        json={
            "partner_id": "PARTNER_X",
            "description": "Scheduled rotation",
            "keys": [{"public_key": keys["rsa2"], "kid": "key-2"}],
            "revoke_kids": ["key-1"],
        },
    )
    assert ru.status_code == 200
    client.post(f"/partners/requests/{ru.json()['id']}/approve", json={})

    active = sorted(k["kid"] for k in client.get("/keys/PARTNER_X").json()["keys"])
    assert active == ["key-2"]
    all_keys = {k["kid"]: k["status"] for k in client.get("/partners/PARTNER_X/keys").json()}
    assert all_keys["key-1"] == "revoked"


def test_disable_enable(client):
    client.post("/partners/PARTNER_X/disable")
    assert client.get("/keys/PARTNER_X").status_code == 404
    assert client.get("/keys/PARTNER_X/jwks.json").status_code == 404
    client.post("/partners/PARTNER_X/enable")
    assert client.get("/keys/PARTNER_X").status_code == 200


def test_reject_path(client, keys):
    client.post(
        "/partners/requests/onboarding",
        json={"partner_id": "PARTNER_Y", "name": "Y", "keys": [{"public_key": keys["ed"]}]},
    )
    reqs = client.get("/partners/requests", params={"partner_id": "PARTNER_Y"}).json()["requests"]
    yreq = reqs[0]["id"]
    assert client.post(f"/partners/requests/{yreq}/reject", json={"notes": "no"}).json()["status"] == "rejected"
    assert client.get("/keys/PARTNER_Y").status_code == 404
    # A decided request cannot be approved.
    assert client.post(f"/partners/requests/{yreq}/approve", json={}).status_code == 400
