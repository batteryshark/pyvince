#!/bin/bash

# Run comprehensive tests for API Key Manager

set -e

echo "🧪 Running API Key Manager Tests"
echo "========================================"

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Starting Redis..."
    if command -v docker &> /dev/null; then
        docker run -d --name test-redis -p 6379:6379 redis/redis-stack:7.2.0-v10
        echo "✅ Started Redis in Docker"
        sleep 5
    else
        echo "❌ Please start Redis manually or install Docker"
        exit 1
    fi
fi

# Install test dependencies
echo "📦 Installing test dependencies..."
pip install pytest pytest-asyncio pytest-cov httpx

# Run tests with coverage
echo "🔍 Running tests with coverage..."
pytest -v \
    --cov=src \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-fail-under=85 \
    tests/

echo ""
echo "✅ Tests completed successfully!"
echo "📊 Coverage report generated in htmlcov/"
echo ""

# Run specific acceptance criteria tests
echo "🎯 Running Acceptance Criteria Tests"
echo "===================================="

echo "1. Happy path validation (< 20ms)..."
pytest -v tests/test_api.py::TestValidateKeyEndpoint::test_validate_key_success

echo "2. Bad secret handling..."
pytest -v tests/test_api.py::TestValidateKeyEndpoint::test_validate_key_wrong_secret

echo "3. Disabled/expired key handling..."
pytest -v tests/test_api.py::TestValidateKeyEndpoint::test_validate_key_disabled
pytest -v tests/test_api.py::TestValidateKeyEndpoint::test_validate_key_expired

echo "4. Rate limiting..."
pytest -v tests/test_api.py::TestIntegrationFlow::test_rate_limiting_flow

echo "5. Key mint/revoke..."
pytest -v tests/test_api.py::TestMintKeyEndpoint::test_mint_key_success
pytest -v tests/test_api.py::TestRevokeKeyEndpoint::test_revoke_key_success

echo "6. Key listing..."
pytest -v tests/test_api.py::TestListKeysEndpoint::test_list_keys_success

echo "7. Integration flow..."
pytest -v tests/test_api.py::TestIntegrationFlow::test_complete_key_lifecycle

echo ""
echo "🎉 All acceptance criteria tests passed!"

# Cleanup test Redis if we started it
if docker ps | grep -q test-redis; then
    echo "🧹 Cleaning up test Redis..."
    docker stop test-redis && docker rm test-redis
fi
