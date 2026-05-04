"""사이트 로그인 + 쿠키 + brute-force 가드."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_me_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False}


def test_login_with_correct_token_sets_cookie(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"token": "test-secret-token"})
    assert r.status_code == 200
    assert "kss_owner" in client.cookies

    r2 = client.get("/api/me")
    assert r2.json() == {"authenticated": True}


def test_login_with_wrong_token_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"token": "wrong"})
    assert r.status_code == 401


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})
    assert client.get("/api/me").json()["authenticated"] is True
    client.post("/api/auth/logout")
    assert client.get("/api/me").json()["authenticated"] is False


def test_brute_force_rate_limit(client: TestClient) -> None:
    for _ in range(5):
        r = client.post("/api/auth/login", json={"token": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"token": "wrong"})
    assert r.status_code == 429
    assert r.headers.get("retry-after") == "60"
