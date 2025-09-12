import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

sys.path.insert(
    0, os.path.abspath("../..")
)  # Adds the parent directory to the system path
import litellm
from litellm import completion
from litellm.integrations.stripe import StripeLogger


def test_stripe_logger_init():
    """Test StripeLogger initialization"""
    # Test missing environment variables
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(Exception) as exc_info:
            StripeLogger()
        assert "Missing keys" in str(exc_info.value)
        assert "STRIPE_API_KEY" in str(exc_info.value)
        assert "STRIPE_PRICE_ID" in str(exc_info.value)
    
    # Test successful initialization
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123"
    }):
        logger = StripeLogger()
        assert logger is not None


def test_stripe_logger_validate_environment():
    """Test environment variable validation"""
    logger = StripeLogger.__new__(StripeLogger)  # Create without calling __init__
    
    # Test with missing API key
    with patch.dict(os.environ, {"STRIPE_PRICE_ID": "price_123"}, clear=True):
        with pytest.raises(Exception) as exc_info:
            logger.validate_environment()
        assert "STRIPE_API_KEY" in str(exc_info.value)
    
    # Test with missing price ID
    with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_123"}, clear=True):
        with pytest.raises(Exception) as exc_info:
            logger.validate_environment()
        assert "STRIPE_PRICE_ID" in str(exc_info.value)
    
    # Test with all required variables
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123"
    }):
        logger.validate_environment()  # Should not raise


def test_stripe_logger_common_logic():
    """Test the common logic for building usage record data"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123", 
        "STRIPE_PRICE_ID": "price_123",
        "STRIPE_CHARGE_BY": "end_user_id"
    }):
        logger = StripeLogger()
        
        # Mock response object
        response_obj = MagicMock()
        response_obj.get.return_value = "test_call_id"
        response_obj.__getitem__ = MagicMock()
        response_obj.__getitem__.return_value.get.return_value = 100
        response_obj.usage = {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}
        
        # Mock kwargs
        kwargs = {
            "response_cost": 0.01,
            "model": "gpt-3.5-turbo",
            "litellm_params": {
                "metadata": {
                    "user_api_key_user_id": "user_123",
                    "user_api_key_team_id": "team_123"
                },
                "proxy_server_request": {
                    "body": {
                        "user": "end_user_123"
                    }
                }
            }
        }
        
        result = logger._common_logic(kwargs, response_obj)
        
        assert "quantity" in result
        assert "timestamp" in result
        assert "action" in result
        assert "idempotency_key" in result
        assert "metadata" in result
        assert result["action"] == "increment"
        assert result["quantity"] == 100  # total tokens
        assert result["metadata"]["model"] == "gpt-3.5-turbo"
        assert result["metadata"]["customer_id"] == "end_user_123"


def test_stripe_logger_charge_by_options():
    """Test different charging options"""
    base_env = {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123"
    }
    
    kwargs = {
        "response_cost": 0.01,
        "model": "gpt-3.5-turbo", 
        "litellm_params": {
            "metadata": {
                "user_api_key_user_id": "user_123",
                "user_api_key_team_id": "team_123"
            },
            "proxy_server_request": {
                "body": {
                    "user": "end_user_123"
                }
            }
        }
    }
    
    response_obj = MagicMock()
    response_obj.get.return_value = "test_call_id"
    response_obj.usage = {"total_tokens": 100}
    
    # Test charge by end_user_id (default)
    with patch.dict(os.environ, {**base_env, "STRIPE_CHARGE_BY": "end_user_id"}):
        logger = StripeLogger()
        result = logger._common_logic(kwargs, response_obj)
        assert result["metadata"]["customer_id"] == "end_user_123"
    
    # Test charge by user_id
    with patch.dict(os.environ, {**base_env, "STRIPE_CHARGE_BY": "user_id"}):
        logger = StripeLogger()
        result = logger._common_logic(kwargs, response_obj)
        assert result["metadata"]["customer_id"] == "user_123"
    
    # Test charge by team_id
    with patch.dict(os.environ, {**base_env, "STRIPE_CHARGE_BY": "team_id"}):
        logger = StripeLogger()
        result = logger._common_logic(kwargs, response_obj)
        assert result["metadata"]["customer_id"] == "team_123"


def test_stripe_logger_invalid_charge_by():
    """Test invalid STRIPE_CHARGE_BY value"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123", 
        "STRIPE_CHARGE_BY": "invalid_option"
    }):
        logger = StripeLogger()
        
        kwargs = {"response_cost": 0.01, "model": "test", "litellm_params": {"metadata": {}}}
        response_obj = MagicMock()
        response_obj.usage = {"total_tokens": 100}
        
        with pytest.raises(Exception) as exc_info:
            logger._common_logic(kwargs, response_obj)
        assert "invalid STRIPE_CHARGE_BY set" in str(exc_info.value)


def test_stripe_logger_missing_customer_id():
    """Test error when customer ID cannot be determined"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123",
        "STRIPE_CHARGE_BY": "end_user_id"
    }):
        logger = StripeLogger()
        
        kwargs = {
            "response_cost": 0.01,
            "model": "test",
            "litellm_params": {
                "metadata": {},
                "proxy_server_request": {"body": {}}  # No user field
            }
        }
        response_obj = MagicMock()
        response_obj.usage = {"total_tokens": 100}
        
        with pytest.raises(Exception) as exc_info:
            logger._common_logic(kwargs, response_obj)
        assert "Customer ID is not set" in str(exc_info.value)


def test_stripe_logger_sync_log_success():
    """Test synchronous success logging"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123"
    }):
        logger = StripeLogger()
        
        # Mock the HTTP handler
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        logger.sync_http_handler.post = MagicMock(return_value=mock_response)
        
        kwargs = {
            "response_cost": 0.01,
            "model": "gpt-3.5-turbo",
            "litellm_params": {
                "metadata": {"user_api_key_user_id": "user_123"},
                "proxy_server_request": {"body": {"user": "end_user_123"}}
            }
        }
        
        response_obj = MagicMock()
        response_obj.get.return_value = "test_call_id"
        response_obj.usage = {"total_tokens": 100}
        
        # Should not raise
        logger.log_success_event(kwargs, response_obj, None, None)
        
        # Verify HTTP call was made
        logger.sync_http_handler.post.assert_called_once()
        call_args = logger.sync_http_handler.post.call_args
        assert "api.stripe.com" in call_args.kwargs["url"]
        assert "price_123" in call_args.kwargs["url"]
        assert "Bearer sk_test_123" in call_args.kwargs["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_stripe_logger_async_log_success():
    """Test asynchronous success logging"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123", 
        "STRIPE_PRICE_ID": "price_123"
    }):
        logger = StripeLogger()
        
        # Mock the async HTTP handler
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = '{"id": "usage_123"}'
        logger.async_http_handler.post = AsyncMock(return_value=mock_response)
        
        kwargs = {
            "response_cost": 0.01,
            "model": "gpt-3.5-turbo", 
            "litellm_params": {
                "metadata": {"user_api_key_user_id": "user_123"},
                "proxy_server_request": {"body": {"user": "end_user_123"}}
            }
        }
        
        response_obj = MagicMock()
        response_obj.get.return_value = "test_call_id"
        response_obj.usage = {"total_tokens": 100}
        
        # Should not raise
        await logger.async_log_success_event(kwargs, response_obj, None, None)
        
        # Verify async HTTP call was made
        logger.async_http_handler.post.assert_called_once()
        call_args = logger.async_http_handler.post.call_args
        assert "api.stripe.com" in call_args.kwargs["url"]
        assert "price_123" in call_args.kwargs["url"]


def test_stripe_callback_integration():
    """Test Stripe callback integration with completion"""
    with patch.dict(os.environ, {
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_PRICE_ID": "price_123"
    }):
        # Mock the completion function to avoid actual API calls
        with patch("litellm.completion") as mock_completion:
            mock_response = MagicMock()
            mock_response.usage = {"total_tokens": 100}
            mock_completion.return_value = mock_response
            
            # Mock StripeLogger to avoid actual HTTP calls
            with patch("litellm.integrations.stripe.StripeLogger") as MockStripeLogger:
                mock_logger = MagicMock()
                MockStripeLogger.return_value = mock_logger
                
                # Test that callback is properly registered
                response = completion(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hello"}],
                    success_callback=["stripe"],
                    litellm_params={
                        "metadata": {"user_api_key_user_id": "user_123"},
                        "proxy_server_request": {"body": {"user": "end_user_123"}}
                    }
                )
                
                # Verify logger was initialized
                MockStripeLogger.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])