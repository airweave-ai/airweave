# S3 Destination Testing Guide

This document describes how to run tests for the S3 destination feature.

## Test Types

### 1. Unit Tests (`tests/unit/api/test_s3_endpoints.py`)

Unit tests that mock external dependencies to test S3 endpoint logic in isolation.

**What they test:**
- Feature flag validation
- Input validation and error handling
- Database operations (mocked)
- AWS credential handling (mocked)
- CRUD context parameter passing

**How to run:**
```bash
cd backend
pytest tests/unit/api/test_s3_endpoints.py -v
```

**Requirements:**
- No external dependencies (fully mocked)
- No AWS credentials needed
- No feature flags needed

### 2. E2E Smoke Tests (`tests/e2e/smoke/test_s3_destination.py`)

End-to-end tests that hit real API endpoints. These are divided into three levels:

#### Level 1: Basic API Tests (Always Run)
Tests that don't require S3_DESTINATION feature flag:
- `/s3/status` endpoint availability
- JSON response structure validation
- Error handling for disabled features

**How to run:**
```bash
cd backend/tests/e2e
pytest smoke/test_s3_destination.py::TestS3DestinationAPI::test_get_s3_status_feature_disabled -v
pytest smoke/test_s3_destination.py::TestS3DestinationAPI::test_s3_endpoints_return_json -v
pytest smoke/test_s3_destination.py::TestS3DestinationAPI::test_s3_status_response_structure -v
```

#### Level 2: Feature-Enabled Tests (Requires Feature Flag)
Tests that require S3_DESTINATION feature flag but use invalid AWS credentials:
- Input validation
- Error responses for invalid ARNs
- Missing field validation

**How to run:**
```bash
cd backend/tests/e2e
pytest smoke/test_s3_destination.py --s3-enabled -v
```

**Requirements:**
- S3_DESTINATION feature flag enabled for test organization
- API endpoint access

#### Level 3: Full Flow Tests (Requires Valid AWS Setup)
Complete integration tests with real AWS credentials:
- Test connection with valid IAM role
- Configure S3 destination
- Update configuration
- Delete configuration
- Full lifecycle validation

**How to run:**
```bash
cd backend/tests/e2e

# Set environment variables
export TEST_S3_ROLE_ARN="arn:aws:iam::123456789012:role/airweave-test-role"
export TEST_S3_EXTERNAL_ID="airweave-test-external-id-12345"
export TEST_S3_BUCKET_NAME="test-airweave-synced-data"

pytest smoke/test_s3_destination.py::TestS3DestinationFullFlow --s3-full-flow -v
```

**Requirements:**
- S3_DESTINATION feature flag enabled
- Valid AWS IAM role configured with:
  - Trust policy allowing Airweave to assume the role
  - External ID matching TEST_S3_EXTERNAL_ID
  - S3 permissions for TEST_S3_BUCKET_NAME
- IAM user credentials stored in Azure Key Vault (or local env vars for dev)

## Running All Tests

### Unit Tests Only
```bash
cd backend
pytest tests/unit/api/test_s3_endpoints.py -v
```

### All S3 Tests (Unit + E2E Basic)
```bash
cd backend
pytest tests/unit/api/test_s3_endpoints.py tests/e2e/smoke/test_s3_destination.py::TestS3DestinationAPI -v
```

### All Tests Including Full Flow
```bash
# Set AWS test credentials first
export TEST_S3_ROLE_ARN="..."
export TEST_S3_EXTERNAL_ID="..."
export TEST_S3_BUCKET_NAME="..."

cd backend
pytest tests/unit/api/test_s3_endpoints.py tests/e2e/smoke/test_s3_destination.py --s3-enabled --s3-full-flow -v
```

## Test Coverage

### Endpoints Tested
- `POST /s3/configure` - Create/update S3 destination
- `POST /s3/test` - Test S3 connection
- `DELETE /s3/configure` - Delete S3 destination
- `GET /s3/status` - Get S3 configuration status

### Scenarios Covered

#### Happy Paths
- ✅ Create new S3 configuration
- ✅ Update existing S3 configuration
- ✅ Test valid S3 connection
- ✅ Get status of configured destination
- ✅ Delete S3 configuration

#### Error Paths
- ✅ Feature flag disabled
- ✅ Invalid IAM role ARN
- ✅ Invalid external ID
- ✅ Missing required fields
- ✅ Non-existent bucket
- ✅ AssumeRole access denied
- ✅ Credential decryption errors
- ✅ Delete non-existent configuration

#### Edge Cases
- ✅ Update configuration without existing credentials
- ✅ Status with decryption failure
- ✅ Proper ctx parameter passing to CRUD layer
- ✅ Multiple updates to same configuration

## Setting Up Test AWS Resources

For Level 3 full flow tests, you need a test AWS environment:

### 1. Create Test IAM Role
```bash
# Using the test-customer-setup.sh script
cd /path/to/infra-core/aws
./test-customer-setup.sh
```

This creates:
- S3 bucket: `test-airweave-synced-data-{env}`
- IAM role: `airweave-test-role`
- IAM policy: `airweave-test-access`
- Trust relationship with external ID

### 2. Export Test Variables
```bash
export TEST_S3_ROLE_ARN=$(aws iam get-role --role-name airweave-test-role --query 'Role.Arn' --output text)
export TEST_S3_EXTERNAL_ID="airweave-test-external-id-12345"
export TEST_S3_BUCKET_NAME="test-airweave-synced-data-dev"
```

### 3. Run Full Flow Tests
```bash
cd backend/tests/e2e
pytest smoke/test_s3_destination.py::TestS3DestinationFullFlow --s3-full-flow -v
```

## Continuous Integration

### GitHub Actions
The tests are designed to run in CI with different levels:

```yaml
# Run in all PRs
- name: Unit Tests
  run: pytest tests/unit/api/test_s3_endpoints.py

# Run in PRs that touch S3 code
- name: E2E Basic Tests
  run: pytest tests/e2e/smoke/test_s3_destination.py::TestS3DestinationAPI

# Run nightly with AWS credentials
- name: Full Flow Tests
  env:
    TEST_S3_ROLE_ARN: ${{ secrets.TEST_S3_ROLE_ARN }}
    TEST_S3_EXTERNAL_ID: ${{ secrets.TEST_S3_EXTERNAL_ID }}
    TEST_S3_BUCKET_NAME: ${{ secrets.TEST_S3_BUCKET_NAME }}
  run: pytest tests/e2e/smoke/test_s3_destination.py --s3-full-flow
```

## Debugging Test Failures

### Common Issues

#### 1. "S3_DESTINATION feature not enabled"
**Solution:** Enable feature flag for test organization:
```sql
UPDATE feature_flags SET s3_destination = true WHERE organization_id = '<test-org-id>';
```

#### 2. "AssumeRole access denied"
**Solutions:**
- Verify IAM role ARN is correct
- Check trust policy includes correct AWS account ID
- Verify external ID matches
- Confirm IAM user has AssumeRole permissions

#### 3. "Bucket access denied"
**Solutions:**
- Verify IAM role policy has S3 permissions
- Check bucket policy allows the role
- Confirm bucket exists in correct region

#### 4. "ctx parameter missing"
This should be caught by unit tests. If you see this error:
- All `crud.integration_credential.get()` calls need `ctx=ctx` parameter
- Check the endpoint implementation

### Verbose Logging
```bash
pytest tests/e2e/smoke/test_s3_destination.py -vv -s --log-cli-level=DEBUG
```

## Test Maintenance

When modifying S3 endpoints:
1. Update unit tests if signature changes
2. Add test cases for new error conditions
3. Update E2E tests if response structure changes
4. Update this README if setup requirements change

## Related Documentation
- [AWS Setup Guide](../../../infra-core/aws/README.md)
- [S3 Destination Architecture](../airweave/platform/destinations/s3.py)
- [API Endpoints](../airweave/api/v1/endpoints/s3.py)
