from datetime import datetime, timezone, timedelta
import httpx
from config import settings

class TokenManager:
    _instance = None
    _token: str | None = None
    _expires_at: datetime | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TokenManager, cls).__new__(cls)
        return cls._instance

    def get_token(self) -> str | None:
        """
        Returns the current valid token (J2 Token).
        If the token is missing or expired, it initiates a token exchange.
        """
        if not settings.token_enabled:
            return None

        if self._is_token_valid():
            return self._token

        return self._exchange_token()

    def _is_token_valid(self) -> bool:
        if not self._token or not self._expires_at:
            return False
        
        # Check against current UTC time with a safety buffer (e.g., 60 seconds)
        now = datetime.now(timezone.utc)
        return now < (self._expires_at - timedelta(seconds=60))

    def _exchange_token(self) -> str:
        """
        Exchanges J1 Token for J2 Token.
        """
        if not settings.token_url or not settings.j1_token:
            raise ValueError("TOKEN_URL and J1_TOKEN must be set when TOKEN_ENABLED is True")

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    settings.token_url,
                    json={"key": settings.j1_token},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                data = response.json()
                
                self._token = data.get("token")
                expires_at_str = data.get("expiresAt")
                
                if expires_at_str:
                    # Handle typical ISO formats. 
                    # If Z is present, replace with +00:00 for fromisoformat compatibility in older python versions if needed, 
                    # but usually ok in 3.11+. Safe bet:
                    if expires_at_str.endswith('Z'):
                        expires_at_str = expires_at_str[:-1] + '+00:00'
                    self._expires_at = datetime.fromisoformat(expires_at_str)
                else:
                    # If no expiration, maybe set a default or don't cache forever?
                    # For safety, defaults to 1 hour if parsing fails? 
                    # But better to error if protocol expects it.
                    # Let's assume it's there as per requirement.
                    pass

                return self._token
                
        except Exception as e:
            # Log error or re-raise
            # In a real app we might want logging.
            print(f"[TokenManager] Exchange failed: {e}")
            raise e

token_manager = TokenManager()
