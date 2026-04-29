"""Local credential storage for Codex OAuth."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .exceptions import NotAuthenticatedError


def default_auth_path() -> Path:
    """Return the default Codex OAuth credential path."""
    env_path = os.environ.get("KOREAN_SOCIAL_SIMULATION_CODEX_OAUTH_AUTH_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".korean_social_simulation" / "codex_oauth" / "auth.json"


@dataclass(frozen=True)
class OAuthCredentials:
    """OAuth credentials persisted on the local machine."""

    access: str
    refresh: str
    expires: int
    account_id: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OAuthCredentials:
        """Create credentials from a JSON dictionary."""
        expires_raw = data.get("expires")
        try:
            expires = int(expires_raw) if expires_raw is not None else 0
        except (TypeError, ValueError):
            expires = 0
        return cls(
            access=str(data.get("access") or ""),
            refresh=str(data.get("refresh") or ""),
            expires=expires,
            account_id=str(data.get("account_id") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert credentials to a JSON-safe dictionary."""
        return {
            "type": "oauth",
            "access": self.access,
            "refresh": self.refresh,
            "expires": self.expires,
            "account_id": self.account_id,
        }


class AuthStore:
    """Load and save Codex OAuth credentials."""

    def __init__(self, auth_path: Path | None = None) -> None:
        """Initialize the store.

        Args:
            auth_path: Optional custom credential path.
        """
        self.auth_path = auth_path or default_auth_path()

    def load(self) -> OAuthCredentials:
        """Load credentials from disk.

        Raises:
            NotAuthenticatedError: If no complete credential file exists.
        """
        if not self.auth_path.exists():
            raise NotAuthenticatedError(
                "Not authenticated. Run `python -m "
                "korean_social_simulation.llm.codex_oauth login`."
            )
        data = json.loads(self.auth_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise NotAuthenticatedError("Codex OAuth auth file is invalid.")
        creds = OAuthCredentials.from_dict(data)
        if not (creds.access and creds.refresh and creds.expires and creds.account_id):
            raise NotAuthenticatedError("Codex OAuth auth file is incomplete.")
        return creds

    def save(self, creds: OAuthCredentials) -> None:
        """Persist credentials with user-only file permissions."""
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.auth_path.with_suffix(self.auth_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(creds.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.auth_path)
        self._chmod_user_only(self.auth_path)

    def delete(self) -> None:
        """Delete stored credentials if present."""
        if self.auth_path.exists():
            self.auth_path.unlink()

    @staticmethod
    def _chmod_user_only(path: Path) -> None:
        """Best-effort chmod that prevents group/world access."""
        if os.name == "nt":
            return
        try:
            current = path.stat().st_mode
            path.chmod(
                (current & ~stat.S_IRWXG & ~stat.S_IRWXO)
                | stat.S_IRUSR
                | stat.S_IWUSR
            )
        except OSError:
            return
