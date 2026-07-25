"""Small deterministic safety layer applied before LLM generation."""

import re

CRISIS_PATTERNS = (
    r"\b(kill myself|suicide|want to die|end my life|self[- ]harm)\b",
    r"\b(hurt myself|cannot go on)\b",
)
HIGH_STAKES_PATTERNS = (
    r"\b(diagnose|medical treatment|legal advice|investment advice|financial advice)\b",
)


def safety_response(query: str) -> str | None:
    """Return a direct safety response when the query needs one."""
    normalized = query.lower()
    if any(re.search(pattern, normalized) for pattern in CRISIS_PATTERNS):
        return (
            "I’m really sorry you’re carrying this. Your immediate safety "
            "matters most: please contact your local emergency number or a "
            "crisis support service now, and reach out to someone you trust "
            "who can stay with you. I can remain here with you while you take "
            "that next step."
        )
    if any(re.search(pattern, normalized) for pattern in HIGH_STAKES_PATTERNS):
        return (
            "I can offer general spiritual reflection, but I can’t provide "
            "medical, legal, or financial diagnosis or advice. Please consult "
            "a qualified professional for guidance specific to your situation."
        )
    return None
