"""OAuth helpers for the Codex consumer backend."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, cast

import requests

from .exceptions import OAuthFlowError, TokenRefreshError

AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
SCOPE = "openid profile email offline_access"
REDIRECT_URI = "http://localhost:1455/auth/callback"


@dataclass(frozen=True)
class TokenResponse:
    """OAuth token response normalized for local storage."""

    access: str
    refresh: str
    expires_at_ms: int


def _b64url(data: bytes) -> str:
    """Return unpadded base64url text."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE verifier/challenge pair."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def create_state() -> str:
    """Create a random OAuth state value."""
    return secrets.token_hex(16)


def build_authorize_url(*, state: str, code_challenge: str) -> str:
    """Build the OpenAI OAuth authorization URL used by Codex CLI."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "codex_cli_rs",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode an unsigned JWT payload.

    Args:
        token: JWT token text.

    Returns:
        Decoded payload when the token is well formed, otherwise ``None``.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + padding)
        decoded = json.loads(raw.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else None
    except Exception:
        return None


def extract_chatgpt_account_id(payload: dict[str, Any]) -> str | None:
    """Extract the ChatGPT account id claim from an OAuth JWT payload."""
    claim = payload.get("https://api.openai.com/auth")
    if not isinstance(claim, dict):
        return None
    account_id = claim.get("chatgpt_account_id")
    return account_id if isinstance(account_id, str) and account_id else None


def exchange_authorization_code(*, code: str, verifier: str) -> TokenResponse:
    """Exchange an OAuth authorization code for access and refresh tokens."""
    try:
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise OAuthFlowError("Authorization code exchange failed") from exc

    return _parse_token_response(data, OAuthFlowError)


def refresh_access_token(*, refresh_token: str) -> TokenResponse:
    """Refresh an expired access token."""
    try:
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise TokenRefreshError("Token refresh failed") from exc

    return _parse_token_response(data, TokenRefreshError)


def _parse_token_response(
    data: dict[str, Any],
    error_type: type[OAuthFlowError] | type[TokenRefreshError],
) -> TokenResponse:
    """Parse a token endpoint response."""
    access = str(data.get("access_token") or "")
    refresh = str(data.get("refresh_token") or "")
    expires_in = int(data.get("expires_in") or 0)
    if not (access and refresh and expires_in):
        raise error_type("Token response missing required fields")
    return TokenResponse(
        access=access,
        refresh=refresh,
        expires_at_ms=int(time.time() * 1000) + expires_in * 1000,
    )


class OAuthCallbackServer(HTTPServer):
    """Small local HTTP server used during browser login."""

    oauth_result: dict[str, str] | None


class _CallbackHandler(BaseHTTPRequestHandler):
    server_version = "korean-social-simulation-codex-oauth"

    def do_GET(self) -> None:  # noqa: N802
        """Handle the OAuth redirect callback."""
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        server = cast(OAuthCallbackServer, self.server)
        server.oauth_result = {
            "code": (params.get("code") or [""])[0],
            "state": (params.get("state") or [""])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h3>Login complete. You can close this tab.</h3>")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default HTTP server logging."""
        return


def run_local_callback_server(*, timeout_s: int = 180) -> dict[str, str] | None:
    """Wait for a local OAuth callback."""
    try:
        server = OAuthCallbackServer(("127.0.0.1", 1455), _CallbackHandler)
    except OSError as exc:
        raise OAuthFlowError("Port 1455 is unavailable. Use manual login.") from exc

    server.oauth_result = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    start = time.time()
    try:
        while time.time() - start < timeout_s:
            if server.oauth_result and server.oauth_result.get("code"):
                return server.oauth_result
            time.sleep(0.1)
        return None
    finally:
        server.shutdown()
        server.server_close()


def parse_authorization_input(value: str) -> dict[str, str]:
    """Parse a pasted redirect URL or raw authorization code."""
    text = value.strip()
    if not text:
        return {}
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme and parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        return {
            "code": (query.get("code") or [""])[0],
            "state": (query.get("state") or [""])[0],
        }
    if "code=" in text:
        query = urllib.parse.parse_qs(text)
        return {
            "code": (query.get("code") or [""])[0],
            "state": (query.get("state") or [""])[0],
        }
    if "#" in text:
        code, state = text.split("#", 1)
        return {"code": code, "state": state}
    return {"code": text}


def login_via_browser(*, timeout_s: int = 180) -> tuple[str, str] | None:
    """Start the browser login flow and return the auth code/verifier pair."""
    verifier, challenge = generate_pkce()
    state = create_state()
    webbrowser.open(build_authorize_url(state=state, code_challenge=challenge))
    result = run_local_callback_server(timeout_s=timeout_s)
    if not result:
        return None
    if result.get("state") and result["state"] != state:
        raise OAuthFlowError("OAuth state mismatch")
    return result["code"], verifier


def login_manual() -> tuple[str, str]:
    """Run a manual OAuth flow for remote/headless environments."""
    verifier, challenge = generate_pkce()
    state = create_state()
    print("Open this URL in your browser and complete login:\n")
    print(build_authorize_url(state=state, code_challenge=challenge))
    print("\nPaste the full redirect URL or code here:")
    parsed = parse_authorization_input(input("> "))
    code = parsed.get("code")
    if not code:
        raise OAuthFlowError("No authorization code provided")
    if parsed.get("state") and parsed["state"] != state:
        raise OAuthFlowError("OAuth state mismatch")
    return code, verifier
