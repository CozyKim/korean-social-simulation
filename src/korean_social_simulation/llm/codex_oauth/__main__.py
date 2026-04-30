"""Codex OAuth helper CLI — login/logout entry point."""

from __future__ import annotations

import argparse

from .auth import (
    decode_jwt_payload,
    exchange_authorization_code,
    extract_chatgpt_account_id,
    login_manual,
    login_via_browser,
)
from .exceptions import OAuthFlowError
from .store import AuthStore, OAuthCredentials


def main() -> None:
    """Codex OAuth 로그인/로그아웃 CLI 진입점."""
    parser = argparse.ArgumentParser(
        prog="python -m korean_social_simulation.llm.codex_oauth"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser(
        "login",
        help="Codex OAuth로 인증 (브라우저 자동 콜백)",
    )
    login_parser.add_argument(
        "--manual",
        action="store_true",
        help="브라우저 자동 콜백 대신 redirect URL/code 수동 붙여넣기 사용",
    )

    subparsers.add_parser("logout", help="저장된 Codex OAuth 자격증명 삭제")
    args = parser.parse_args()

    if args.command == "logout":
        AuthStore().delete()
        print("Deleted Codex OAuth credentials.")
        return

    try:
        code_and_verifier = login_manual() if args.manual else login_via_browser()
        if code_and_verifier is None:
            raise OAuthFlowError("Timed out waiting for OAuth callback.")
        code, verifier = code_and_verifier
        token_response = exchange_authorization_code(code=code, verifier=verifier)
        payload = decode_jwt_payload(token_response.access)
        account_id = extract_chatgpt_account_id(payload or {})
        if not account_id:
            raise OAuthFlowError("Could not derive ChatGPT account id from token.")
        AuthStore().save(
            OAuthCredentials(
                access=token_response.access,
                refresh=token_response.refresh,
                expires=token_response.expires_at_ms,
                account_id=account_id,
            )
        )
    except OAuthFlowError as exc:
        raise SystemExit(str(exc)) from exc

    print("Codex OAuth login complete.")


if __name__ == "__main__":
    main()
