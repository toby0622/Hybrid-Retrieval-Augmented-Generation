import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.services.auth import TokenManager, token_manager
from config import settings
from app.llm_factory import get_llm

def test_token_exchange():
    print("Testing token exchange...")
    
    # Mock settings
    settings.token_enabled = True
    settings.token_url = "http://mock-auth/token"
    settings.j1_token = "mock-j1-token"
    
    # Mock httpx.Client
    with patch("httpx.Client") as mock_client:
        mock_response = MagicMock()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_response.json.return_value = {
            "token": "mock-j2-token",
            "expiresAt": expires_at,
            "username": "apiId:test"
        }
        mock_response.raise_for_status.return_value = None
        
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        # Reset token manager
        token_manager._token = None
        token_manager._expires_at = None
        
        # Test exchange
        token = token_manager.get_token()
        
        print(f"Token retrieved: {token}")
        assert token == "mock-j2-token"
        assert token_manager._is_token_valid()
        
        # Verify call
        mock_client.return_value.__enter__.return_value.post.assert_called_with(
            "http://mock-auth/token",
            json={"key": "mock-j1-token"},
            headers={"Content-Type": "application/json"}
        )
        print("Token exchange test passed!")

def test_config_injection():
    print("\nTesting LLM Factory injection...")
    
    settings.token_enabled = True
    # Ensure token manager has a token (reusing from previous test or mocking)
    with patch.object(token_manager, "get_token", return_value="mock-j2-token"):
        llm = get_llm()
        
        # Check default headers in underlying client or passed args
        # ChatOpenAI stores default_headers? 
        # It's passed to OpenAI client. access via llm.default_headers if available or check init args
        
        print(f"LLM type: {type(llm)}")
        # Inspect internals if possible or rely on simple attribute check if exposed
        # LangChain ChatOpenAI might exposes `default_headers` or similar?
        # Actually it's `llm.default_headers` (pydantic field)
        
        print(f"Default Headers: {llm.default_headers}")
        assert "Authorization" in llm.default_headers
        assert llm.default_headers["Authorization"] == "mock-j2-token"
        assert llm.default_headers["Content-Type"] == "application/json"
        
        print("LLM Factory test passed!")

if __name__ == "__main__":
    try:
        test_token_exchange()
        test_config_injection()
        print("\nAll verification tests passed successfully!")
    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
