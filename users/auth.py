"""Custom authentication utilities for the users app."""

from django.contrib.auth import get_user_model

User = get_user_model()


def user_authentication_rule(user):
    """Custom authentication rule for SimpleJWT.

    Returns True if the user is allowed to authenticate.
    """
    if user is None:
        return False
    return user.is_active
