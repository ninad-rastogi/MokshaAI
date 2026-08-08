from scripts.live_ui_walkthrough import validate_result


def _passing_result() -> dict[str, object]:
    return {
        "auth_after_refresh": "http://localhost/app",
        "composer_cleared": True,
        "run_state_text": "idle",
        "desktop_geometry": {"bodyScroll": False},
        "mobile_geometry": {"bodyScroll": False},
        "settings_geometry": {"client": 670, "scroll": 670},
        "console_errors": [],
        "request_failures": [],
        "connection_removed": True,
        "primary_model_after_refresh": "Moksha local",
        "connection_status_aria": "Online · Moksha local · qwen3:4b",
        "exact_verse_text": "Exact verse\nउत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
        "translation_text": "Translation\nArise, awake, and learn from the wise.",
    }


def test_live_walkthrough_validator_accepts_clean_mock_result():
    assert validate_result(_passing_result(), mock_api=True) == []


def test_live_walkthrough_validator_rejects_broken_browser_contracts():
    result = _passing_result()
    result.update(
        {
            "auth_after_refresh": "http://localhost/",
            "desktop_geometry": {"bodyScroll": True},
            "connection_status_aria": "Connecting",
            "exact_verse_text": "",
        }
    )

    failures = validate_result(result, mock_api=True)

    assert "auth_refresh_did_not_stay_in_app" in failures
    assert "desktop_body_scrolls" in failures
    assert "model_connection_status_missing_online_model" in failures
    assert "exact_verse_not_visible" in failures
