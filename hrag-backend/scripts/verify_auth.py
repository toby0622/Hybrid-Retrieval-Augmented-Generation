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
    settings.llm_j1_token = "mock-j1-token-llm"
    settings.embed_j1_token = "mock-j1-token-embed"
    
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
        token_manager._tokens = {"llm": None, "embedding": None}
        token_manager._expires_at = {"llm": None, "embedding": None}
        
        # Test exchange for LLM
        token_llm = token_manager.get_token("llm")
        
        print(f"LLM Token retrieved: {token_llm}")
        assert token_llm == "mock-j2-token"
        assert token_manager._is_token_valid("llm")
        
        # Verify call for LLM
        mock_client.return_value.__enter__.return_value.post.assert_any_call(
            "http://mock-auth/token",
            json={"key": "mock-j1-token-llm"},
            headers={"Content-Type": "application/json"}
        )

        # Test exchange for Embedding
        # Reset mock to allow new call (or just check calls)
        # Simplify: assume same return value for now
        token_embed = token_manager.get_token("embedding")
        print(f"Embedding Token retrieved: {token_embed}")
        assert token_embed == "mock-j2-token"
        assert token_manager._is_token_valid("embedding")
        
         # Verify call for Embedding
        mock_client.return_value.__enter__.return_value.post.assert_any_call(
            "http://mock-auth/token",
            json={"key": "mock-j1-token-embed"},
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
