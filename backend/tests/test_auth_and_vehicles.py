from tests.conftest import VEHICLE_PAYLOAD, register


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_register_login_and_me(client):
    client.post("/api/v1/auth/register", json={"email": "Ops@Fleet.in", "password": "s3cure-pass"})

    login = client.post("/api/v1/auth/login", json={"email": "ops@fleet.in", "password": "s3cure-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "ops@fleet.in"


def test_duplicate_email_and_bad_password(client):
    register(client, "a@b.in")
    assert (
        client.post("/api/v1/auth/register", json={"email": "a@b.in", "password": "s3cure-pass"}).status_code
        == 409
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": "a@b.in", "password": "wrong-pass"}).status_code
        == 401
    )


def test_requests_without_token_are_rejected(client):
    assert client.get("/api/v1/vehicles").status_code in (401, 403)
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/v1/vehicles", headers=bad).status_code == 401


def test_vehicle_crud(client, auth_headers, vehicle):
    assert vehicle["vin"] == VEHICLE_PAYLOAD["vin"]

    listed = client.get("/api/v1/vehicles", headers=auth_headers).json()
    assert [v["id"] for v in listed] == [vehicle["id"]]

    patched = client.patch(
        f"/api/v1/vehicles/{vehicle['id']}", json={"nickname": "Cab 01 (spare)"}, headers=auth_headers
    )
    assert patched.json()["nickname"] == "Cab 01 (spare)"

    assert client.delete(f"/api/v1/vehicles/{vehicle['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=auth_headers).status_code == 404


def test_vin_is_validated_and_unique(client, auth_headers, vehicle):
    bad_vin = {**VEHICLE_PAYLOAD, "vin": "MAT612345NX00000I"}  # 'I' is not allowed in a VIN
    assert client.post("/api/v1/vehicles", json=bad_vin, headers=auth_headers).status_code == 422

    lower = {**VEHICLE_PAYLOAD, "vin": VEHICLE_PAYLOAD["vin"].lower()}
    assert client.post("/api/v1/vehicles", json=lower, headers=auth_headers).status_code == 409


def test_users_cannot_see_each_others_vehicles(client, vehicle):
    other = register(client)
    assert client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/vehicles/{vehicle['id']}/telemetry", headers=other).status_code == 404
