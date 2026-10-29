from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, base_url="http://localhost")


def test_health_same_origin_ok():
    assert client.get("/api/health", headers={"sec-fetch-site": "same-origin"}).status_code == 200


def test_cross_site_request_refused():
    r = client.get("/api/health", headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_unknown_host_refused():
    # protège contre le DNS rebinding
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_no_cors_header():
    r = client.get("/api/health", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_inputs_are_bounded():
    assert client.get("/api/zones?bbox=0,40,10,50").status_code == 400          # trop de tuiles
    assert client.get("/api/zones?bbox=abc").status_code == 400
    assert client.get("/api/geocode?q=" + "a" * 500).status_code == 422
    assert client.get("/api/top?lat=48&lon=6&limit=500").status_code == 422
