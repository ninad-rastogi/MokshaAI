import os
import subprocess
import sys


def test_non_debug_cookie_security_flags_can_be_disabled_for_local_http() -> None:
    env = {
        **os.environ,
        "DJANGO_DEBUG": "False",
        "DJANGO_SECRET_KEY": "test-secret-key",
        "DJANGO_SECURE_SSL_REDIRECT": "False",
        "DJANGO_SESSION_COOKIE_SECURE": "False",
        "DJANGO_CSRF_COOKIE_SECURE": "False",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from moksha import settings; "
                "print(settings.SECURE_SSL_REDIRECT); "
                "print(settings.SESSION_COOKIE_SECURE); "
                "print(settings.CSRF_COOKIE_SECURE)"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout.splitlines() == ["False", "False", "False"]
