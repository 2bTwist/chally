# Test Scripts

This directory contains test scripts that handle complex testing scenarios that require special handling.

## Scripts

### `test_auth.sh`
Authentication test suite that runs tests individually to avoid async conflicts.

**Usage:**
```bash
# From project root
./backend/tests/scripts/test_auth.sh

# Or via Makefile
make test-script
```

**What it tests:**
- Main authentication flow (register, login, /me)
- Duplicate email validation
- Duplicate username validation

## Why Individual Scripts?

Some test scenarios have specific requirements:
- **Authentication tests**: Run individually to avoid async/database connection conflicts
- **Integration tests**: May need special setup/teardown
- **Performance tests**: Require isolated execution environments

## Adding New Scripts

When adding new test scripts:
1. Make them executable: `chmod +x script_name.sh`
2. Add proper error handling and exit codes
3. Include progress indicators for better UX
4. Document the script purpose in this README
5. Add a corresponding `make` target in the root Makefile