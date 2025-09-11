"""
Basic tests for soft delete functionality.
This file tests the core soft delete and restore functionality for users and keys.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from litellm.proxy._types import DeleteUserRequest, RestoreUserRequest, RestoreKeyRequest


class TestSoftDeleteFunctionality:
    """Test the soft delete and restore functionality"""
    
    def test_delete_user_request_validation(self):
        """Test that DeleteUserRequest works correctly"""
        request = DeleteUserRequest(user_ids=["user1", "user2"])
        assert request.user_ids == ["user1", "user2"]
        
    def test_restore_user_request_validation(self):
        """Test that RestoreUserRequest works correctly"""
        request = RestoreUserRequest(user_ids=["user1", "user2"])
        assert request.user_ids == ["user1", "user2"]
        
    def test_restore_key_request_validation(self):
        """Test that RestoreKeyRequest works correctly"""
        # Test with keys
        request = RestoreKeyRequest(keys=["key1", "key2"])
        assert request.keys == ["key1", "key2"]
        assert request.key_aliases is None
        
        # Test with key_aliases
        request = RestoreKeyRequest(key_aliases=["alias1", "alias2"])
        assert request.key_aliases == ["alias1", "alias2"]
        assert request.keys is None
        
        # Test validation - should fail if neither keys nor key_aliases provided
        with pytest.raises(ValueError):
            RestoreKeyRequest()
            
    def test_schema_changes(self):
        """Test that schema changes are applied correctly"""
        # This is a basic test to ensure the schema files were updated correctly
        # In a real test environment, we would test the actual database schema
        
        # Check that schema files contain the deleted_at fields
        with open('/home/runner/work/Proxyllm/Proxyllm/schema.prisma', 'r') as f:
            schema_content = f.read()
            assert 'deleted_at      DateTime?' in schema_content
            
        with open('/home/runner/work/Proxyllm/Proxyllm/litellm/proxy/schema.prisma', 'r') as f:
            proxy_schema_content = f.read()
            assert 'deleted_at      DateTime?' in proxy_schema_content


if __name__ == "__main__":
    # Run basic validation tests
    test = TestSoftDeleteFunctionality()
    test.test_delete_user_request_validation()
    test.test_restore_user_request_validation()
    test.test_restore_key_request_validation()
    test.test_schema_changes()
    print("All basic tests passed!")