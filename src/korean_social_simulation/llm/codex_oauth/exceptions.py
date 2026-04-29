"""Exceptions for the Codex OAuth integration."""

from __future__ import annotations


class CodexOAuthError(Exception):
    """Base exception for Codex OAuth failures."""


class OAuthFlowError(CodexOAuthError):
    """Raised when the browser/manual OAuth flow fails."""


class TokenRefreshError(CodexOAuthError):
    """Raised when a refresh token cannot produce a new access token."""


class NotAuthenticatedError(CodexOAuthError):
    """Raised when no valid local OAuth credentials are available."""


class CodexBackendError(CodexOAuthError):
    """Raised when the ChatGPT Codex backend rejects a request."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize the backend error.

        Args:
            message: Human-readable error message.
            status_code: Optional HTTP status code returned by the backend.
        """
        super().__init__(message)
        self.status_code = status_code
