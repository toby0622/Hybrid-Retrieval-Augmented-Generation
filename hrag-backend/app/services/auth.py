from datetime import datetime, timedelta, timezone

import httpx
from app.core.config import settings


class TokenManager:
    _instance = None
    _tokens: dict[str, str | None] = {}
    _expires_at: dict[str, datetime | None] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TokenManager, cls).__new__(cls)
            cls._instance._tokens = {"llm": None, "embedding": None}
            cls._instance._expires_at = {"llm": None, "embedding": None}
        return cls._instance

    def get_token(self, token_type: str = "llm") -> str | None:
        if not settings.token_enabled:
            return None

        if self._is_token_valid(token_type):
            return self._tokens.get(token_type)

        return self._exchange_token(token_type)

    def _is_token_valid(self, token_type: str) -> bool:
        token = self._tokens.get(token_type)
        expires_at = self._expires_at.get(token_type)

        if not token or not expires_at:
            return False

        now = datetime.now(timezone.utc)
        return now < (expires_at - timedelta(seconds=60))

    def _exchange_token(self, token_type: str) -> str:
        if not settings.token_url:
            raise ValueError("TOKEN_URL must be set when TOKEN_ENABLED is True")

        j1_token = None
        if token_type == "llm":
            j1_token = settings.llm_j1_token
        elif token_type == "embedding":
            j1_token = settings.embed_j1_token

        if not j1_token:
            raise ValueError(
                f"{token_type.upper()}_J1_TOKEN must be set when TOKEN_ENABLED is True"
            )

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    settings.token_url,
                    json={"key": j1_token},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                self._tokens[token_type] = data.get("token")
                expires_at_str = data.get("expiresAt")

                if expires_at_str:
                    if expires_at_str.endswith("Z"):
                        expires_at_str = expires_at_str[:-1] + "+00:00"
                    self._expires_at[token_type] = datetime.fromisoformat(
                        expires_at_str
                    )
                else:
                    pass

                return self._tokens[token_type]

        except Exception as e:
            print(f"[TokenManager] Exchange failed for {token_type}: {e}")
            raise e


token_manager = TokenManager()
