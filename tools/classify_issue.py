"""Rule-based issue classification from agent descriptions."""

from __future__ import annotations

import re

CATEGORY_RULES: list[tuple[str, list[str], float]] = [
    ("LATENCY", ["spinning", "latency", "slow", "frozen", "froze", "stuck", "struck", "hang", "loading", "unresponsive"], 0.8),
    ("UI_ERROR", ["greyed out", "grayed out", "won't update", "wont update", "does not bring up", "doesn't bring up", "not bring up", "click edit", "won't let me", "wont let me", "not available"], 0.75),
    ("AUTH_ERROR", ["authenticate", "authentication", "token expired", "token not found", "unauthorized", "login", "caller card multiple"], 0.85),
    ("DATA_ERROR", ["conversion of value", "format", "invalid value", "not valid for", "field.*failed"], 0.9),
]


def classify_issue(description: str, error_data: str = "") -> dict:
    """Classify an issue based on description text and optional error data."""
    combined_text = f"{description} {error_data}".lower()

    best_category = "UNKNOWN"
    best_confidence = 0.0
    matched_keywords: list[str] = []

    for category, keywords, base_confidence in CATEGORY_RULES:
        category_matches = []
        for keyword in keywords:
            if re.search(keyword, combined_text):
                category_matches.append(keyword)

        if category_matches:
            match_boost = min(len(category_matches) * 0.05, 0.15)
            confidence = min(base_confidence + match_boost, 1.0)

            if confidence > best_confidence:
                best_category = category
                best_confidence = confidence
                matched_keywords = category_matches

    has_clear_error = bool(error_data and ("code" in error_data.lower() or "exception" in error_data.lower()))
    recording_review_needed = best_category == "UNKNOWN" or (best_confidence < 0.7 and not has_clear_error)

    return {
        "category": best_category,
        "confidence": round(best_confidence, 2),
        "recording_review_needed": recording_review_needed,
        "matched_keywords": matched_keywords,
    }
