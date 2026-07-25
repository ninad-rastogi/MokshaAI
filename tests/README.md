# tests/ — Test Suite

This directory contains the **test suite** for Moksha AI. Tests are written using
`pytest` with `pytest-django` for database support.

## Purpose

The test suite covers:
- **Model tests**: Verify database models work correctly (creation, validation, relationships)
- **View tests**: Verify API endpoints return correct responses
- **Integration tests**: End-to-end flows (register → login → chat → verify)
- **RAG tests**: Query routing, embedding search, chunking logic

## Files

### `conftest.py` — Shared Fixtures

Defines pytest fixtures used across all test files:

- **`api_client`**: Unauthenticated DRF `APIClient` instance
- **`create_user`**: Factory fixture that creates User instances with given email/password
- **`authenticated_client`**: Returns a tuple of `(APIClient, User)` where the client
  has valid JWT authentication. Registers, logs in, and sets the Authorization header.

### `integration/test_chat_flow.py` — End-to-End Flow Test

Tests the complete user journey:
1. Register a new account
2. Login and get JWT token
3. Get user profile
4. Create a new chat
5. List chats
6. Submit a query (gets placeholder response)
7. Verify chat has messages
8. Rename the chat
9. Delete the chat

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Stop on first failure
pytest -x

# Specific test file
pytest users/tests/test_models.py

# Specific test class
pytest users/tests/test_views.py::TestRegisterView

# Specific test
pytest users/tests/test_models.py::TestUserModel::test_create_user
```

## Test Database

pytest-django automatically creates a test database (prefixed with `test_`) for each
test run. No need to configure a separate test database.

## Adding New Tests

1. Create test file in the appropriate `tests/` subdirectory
2. Use `@pytest.mark.django_db` for tests that need database access
3. Import fixtures from `conftest.py` as function parameters
4. Follow the naming convention: `test_<what_is_being_tested>`
