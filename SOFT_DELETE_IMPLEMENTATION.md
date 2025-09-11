# Soft Delete Implementation for LiteLLM Proxy

## Overview

This implementation adds comprehensive soft delete functionality to the LiteLLM proxy for both users and API keys, addressing enterprise requirements for audit trail maintenance and data integrity.

## Key Features

### ✅ Implemented Features

1. **Soft Delete for Users**
   - Users are marked as deleted with `deleted_at` timestamp instead of being removed
   - User deletion automatically soft-deletes all associated keys
   - Deleted users are excluded from default queries
   - Team memberships and invitation links are properly cleaned up

2. **Soft Delete for Keys**
   - API keys are marked as deleted with `deleted_at` timestamp
   - Keys can be soft deleted individually or via user deletion
   - Deleted keys are excluded from default queries

3. **Restore Functionality**
   - Soft-deleted users can be restored via `/user/restore` endpoint
   - Soft-deleted keys can be restored via `/key/restore` endpoint
   - **Security Feature**: Restored users do NOT get their old keys back (must generate new ones)

4. **Query Filtering**
   - All list endpoints now have `include_deleted` parameter (defaults to `false`)
   - UI can toggle viewing of deleted items by setting `include_deleted=true`
   - Default behavior excludes soft-deleted items for normal operations

5. **Data Integrity**
   - Spend logs maintain references to deleted users/keys for reporting
   - Audit logs preserved for all soft delete/restore operations
   - Foreign key relationships maintained

## Database Schema Changes

### Added to `LiteLLM_UserTable`:
```prisma
deleted_at DateTime? @map("deleted_at")
```

### Added to `LiteLLM_VerificationToken`:
```prisma
deleted_at DateTime? @map("deleted_at")
```

## API Endpoints

### New Endpoints

#### User Management
- `POST /user/restore` - Restore soft-deleted users
  ```json
  {
    "user_ids": ["user-id-1", "user-id-2"]
  }
  ```

#### Key Management  
- `POST /key/restore` - Restore soft-deleted keys
  ```json
  {
    "keys": ["sk-key1", "sk-key2"]
  }
  ```
  OR
  ```json
  {
    "key_aliases": ["alias1", "alias2"]
  }
  ```

### Modified Endpoints

#### User List
- `GET /user/list?include_deleted=true` - Include soft-deleted users

#### Key List
- `GET /key/list?include_deleted=true` - Include soft-deleted keys

## Implementation Details

### User Deletion Flow
1. Validate user exists and is not already deleted
2. Clean up team memberships and roles
3. Soft delete all user's keys (`deleted_at = now()`)
4. Hard delete invitation links and organization memberships (safe to remove)
5. Soft delete user (`deleted_at = now()`)
6. Create audit log entry

### Key Deletion Flow
1. Validate key exists and user has permission
2. Set `deleted_at = now()` on verification token
3. Remove from cache
4. Create audit log entry

### Restore Flow
1. Validate item exists and is actually deleted (`deleted_at IS NOT NULL`)
2. Set `deleted_at = NULL`
3. For users: Do NOT restore keys (security requirement)
4. Create audit log entry

### Query Filtering
All queries now include:
```sql
WHERE deleted_at IS NULL  -- When include_deleted=false (default)
```

## Security Considerations

1. **Key Security**: Restored users must generate new API keys for security
2. **Permission Checks**: Only authorized users can delete/restore based on existing permission model
3. **Audit Trail**: All operations are logged for compliance
4. **Data Isolation**: Deleted items are hidden from normal operations but preserved for auditing

## Testing

Comprehensive tests validate:
- Type definitions and request validation
- Soft delete functionality prevents data loss
- Restore functionality works correctly
- Query filtering excludes deleted items by default
- Schema changes are properly applied
- All endpoints handle edge cases (already deleted, not found, etc.)

## Migration Notes

- This is a backward-compatible change
- Existing data will have `deleted_at = NULL` (not deleted)
- No immediate database migration required
- New behavior takes effect immediately for new deletions

## Benefits

1. **Enterprise Compliance**: Maintains complete audit trail
2. **Data Integrity**: Spend logs and reporting remain accurate
3. **Recovery**: Accidentally deleted users/keys can be restored
4. **Flexibility**: UI can choose to show/hide deleted items
5. **Security**: Restored users must generate fresh credentials

## Files Modified

1. `schema.prisma` - Added deleted_at fields
2. `litellm/proxy/schema.prisma` - Added deleted_at fields
3. `litellm/proxy/_types.py` - Added new request types
4. `litellm/proxy/management_endpoints/internal_user_endpoints.py` - Soft delete + restore for users
5. `litellm/proxy/management_endpoints/key_management_endpoints.py` - Soft delete + restore for keys
6. `litellm/proxy/utils.py` - Updated delete_data to use soft delete

## Usage Examples

### Delete and Restore User
```bash
# Soft delete user
curl -X POST "http://localhost:4000/user/delete" \
  -H "Authorization: Bearer sk-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user-123"]}'

# List users (deleted user not shown)
curl "http://localhost:4000/user/list"

# List users including deleted
curl "http://localhost:4000/user/list?include_deleted=true"

# Restore user (keys NOT restored)
curl -X POST "http://localhost:4000/user/restore" \
  -H "Authorization: Bearer sk-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user-123"]}'
```

### Delete and Restore Key
```bash
# Soft delete key
curl -X POST "http://localhost:4000/key/delete" \
  -H "Authorization: Bearer sk-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["sk-key-123"]}'

# Restore key
curl -X POST "http://localhost:4000/key/restore" \
  -H "Authorization: Bearer sk-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["sk-key-123"]}'
```