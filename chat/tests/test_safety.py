"""Tests for deterministic safety handling before model generation."""

from chat.rag.safety import safety_response


def test_crisis_language_bypasses_generation():
    response = safety_response("I want to kill myself")
    assert response is not None
    assert "emergency" in response.lower()


def test_high_stakes_request_gets_professional_boundary():
    response = safety_response("Can you give me medical treatment?")
    assert response is not None
    assert "qualified professional" in response.lower()


def test_ordinary_spiritual_question_reaches_rag():
    assert safety_response("What does this text teach about ethical action?") is None
