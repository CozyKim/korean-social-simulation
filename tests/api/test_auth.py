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


def test_login_cookie_defaults_to_lax_insecure(client: TestClient) -> None:
    """기본값은 SameSite=Lax + Secure 미적용 (개발 환경)."""
    r = client.post("/api/auth/login", json={"token": "test-secret-token"})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    # 기본 dev 환경 — Lax 이고 Secure 플래그 없음.
    assert "samesite=lax" in set_cookie.lower()
    assert "secure" not in set_cookie.lower()


def test_login_cookie_respects_cross_site_settings(tmp_path, monkeypatch) -> None:
    """KSS_COOKIE_SAMESITE=none + KSS_COOKIE_SECURE=true 시 cross-site 쿠키 발급."""
    from fastapi.testclient import TestClient

    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter

    monkeypatch.setenv("KSS_OWNER_TOKEN", "test-secret-token")
    monkeypatch.setenv("KSS_COOKIE_SECRET", "test-cookie-secret-key")
    monkeypatch.setenv("KSS_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("KSS_SCENARIOS_ROOT", str(tmp_path / "scenarios"))
    monkeypatch.setenv("KSS_CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("KSS_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("KSS_COOKIE_SECURE", "true")
    (tmp_path / "runs").mkdir()
    (tmp_path / "scenarios").mkdir()

    get_limiter().reset()
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"token": "test-secret-token"})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    lower = set_cookie.lower()
    assert "samesite=none" in lower, set_cookie
    assert "secure" in lower, set_cookie
