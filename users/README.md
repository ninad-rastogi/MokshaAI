# users/ — Authentication & User Management App

This Django app handles **user registration, authentication, and profile management**.
It replaces the old system that had no authentication at all.

## Purpose

In the old codebase, there were no users — anyone could access everything. This app introduces:
- User accounts with email-based login (no usernames)
- JWT token authentication for API access
- User profile management
- Django admin integration for user management

## Files

### `models.py` — Custom User Model
Defines `User` model extending Django's `AbstractUser`:
- **Email as primary key**: `username = None`, `USERNAME_FIELD = "email"`
- **Unique email**: `email = models.EmailField(unique=True)`
- **Spiritual name**: Optional `spiritual_name` field for a user's spiritual identity
- **Timestamps**: `created_at` auto-set on creation
- This model is referenced by `AUTH_USER_MODEL = "users.User"` in settings

### `serializers.py` — DRF Serializers
Two serializers:
- **`UserSerializer`**: Read-only profile data (id, email, spiritual_name, created_at)
- **`RegisterSerializer`**: Handles registration with password validation:
  - Requires password + password_confirm (must match)
  - Minimum 8 character password
  - Creates user via `create_user()` (properly hashes password)

### `views.py` — API Views
Three views:
- **`RegisterView`** (`POST /api/auth/register/`): Creates new user, returns user data.
  No authentication required.
- **`ProfileView`** (`GET/PUT /api/auth/me/`): Get or update current user profile.
  Requires authentication.
- **`HealthCheckView`** (`GET /api/auth/health/`): Returns `{"status": "ok"}`.
  No authentication required. Used by Streamlit to check if backend is running.

### `urls.py` — URL Routes
| URL | View | Name |
|-----|------|------|
| `register/` | `RegisterView` | `register` |
| `login/` | `TokenRefreshView` (SimpleJWT) | `login` |
| `refresh/` | `TokenRefreshView` (SimpleJWT) | `token-refresh` |
| `me/` | `ProfileView` | `profile` |
| `health/` | `HealthCheckView` | `health` |

Note: Login uses SimpleJWT's built-in token obtain/refresh views.

### `admin.py` — Django Admin
`CustomUserAdmin` configures the admin panel:
- List display: email, spiritual_name, is_staff, created_at
- Search: email, spiritual_name
- Fieldsets organized for email-based auth (no username)
- Add fieldsets for creating new users

### `apps.py`
Django app configuration. Sets `verbose_name = "User Management"`.

## Tests

### `tests/test_models.py`
Tests for the User model:
- Creating regular users and superusers
- Email uniqueness enforcement
- Spiritual name (optional field)
- String representation

### `tests/test_views.py`
Tests for API endpoints:
- Registration (success, password mismatch, duplicate email)
- Profile access (authenticated vs unauthenticated)
- Health check endpoint
