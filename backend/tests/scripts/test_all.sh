#!/bin/bash

# Test suite - runs tests individually to avoid async conflicts

echo "🧪 Running All Tests"
echo "===================="

# Track test results
FAILED_TESTS=()

# Test 1: Main auth functionality
if docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api python -m pytest tests/test_auth.py -q > /tmp/test1.log 2>&1; then
    echo "✅ Main auth: PASSED"
else
    echo "❌ Main auth: FAILED"
    FAILED_TESTS+=("Main auth")
fi

# Test 2: Duplicate email validation
if docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api python -m pytest tests/test_auth_duplicates.py::test_duplicate_email -q > /tmp/test2.log 2>&1; then
    echo "✅ Duplicate email: PASSED"
else
    echo "❌ Duplicate email: FAILED"
    FAILED_TESTS+=("Duplicate email")
fi

# Test 3: Duplicate username validation
if docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api python -m pytest tests/test_auth_duplicates.py::test_duplicate_username -q > /tmp/test3.log 2>&1; then
    echo "✅ Duplicate username: PASSED"
else
    echo "❌ Duplicate username: FAILED"
    FAILED_TESTS+=("Duplicate username")
fi

# Test 4: Challenge functionality
if docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api python -m pytest tests/test_challenges.py -q > /tmp/test4.log 2>&1; then
    echo "✅ Challenges: PASSED"
else
    echo "❌ Challenges: FAILED"
    FAILED_TESTS+=("Challenges")
fi

# Cleanup temp files
rm -f /tmp/test*.log

# Summary
echo ""
if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    echo "🎉 All tests PASSED!"
    exit 0
else
    echo "💥 ${#FAILED_TESTS[@]} test(s) FAILED:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "   - $test"
    done
    exit 1
fi