"""Classify Issue Lambda — Action Group 4.

Rule-based pre-classification of agent-entered descriptions into issue
categories. Flags cases where user interaction recording review is needed.
"""

from __future__ import annotations

import json
import re


# Category keyword mappings (lowercased for matching)
CATEGORY_RULES: list[tuple[str, list[str], float]] = [
    ("LATENCY", ["spinning", "latency", "slow", "frozen", "froze", "stuck", "struck", "hang", "loading", "unresponsive"], 0.8),
    ("UI_ERROR", ["greyed out", "grayed out", "won't update", "wont update", "does not bring up", "doesn't bring up", "not bring up", "click edit", "won't let me", "wont let me", "not available"], 0.75),
    ("AUTH_ERROR", ["authenticate", "authentication", "token expired", "token not found", "unauthorized", "login", "caller card multiple"], 0.85),
    ("DATA_ERROR", ["conversion of value", "format", "invalid value", "not valid for", "field.*failed"], 0.9),
]


def classify_description(description: str, error_data: str = "") -> dict:
    """Classify an issue based on description text and optional error data.

    Returns category, confidence, whether recording review is needed,
    and which keywords matched.
    """
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
            # More keyword matches = higher confidence
            match_boost = min(len(category_matches) * 0.05, 0.15)
            confidence = min(base_confidence + match_boost, 1.0)

            if confidence > best_confidence:
                best_category = category
                best_confidence = confidence
                matched_keywords = category_matches

    # Determine if recording review is needed
    # Direct error data with SF IDs or clear error codes reduce need for review
    has_clear_error = bool(error_data and ("code" in error_data.lower() or "exception" in error_data.lower()))
    recording_review_needed = best_category == "UNKNOWN" or (best_confidence < 0.7 and not has_clear_error)

    return {
        "category": best_category,
        "confidence": round(best_confidence, 2),
        "recording_review_needed": recording_review_needed,
        "matched_keywords": matched_keywords,
    }


def handler(event, context):
    """Lambda handler for Bedrock Agent action group invocation."""
    action_group = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    request_body = event.get("requestBody", {})

    # Extract parameters from request body
    description = ""
    error_data = ""

    if request_body and "content" in request_body:
        content = request_body["content"]
        if "application/json" in content:
            properties = content["application/json"].get("properties", [])
            for prop in properties:
                if prop["name"] == "description":
                    description = prop["value"]
                elif prop["name"] == "error_data":
                    error_data = prop["value"]

    classification = classify_description(description, error_data)

    response_body = {"application/json": {"body": json.dumps(classification)}}

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": "POST",
            "httpStatusCode": 200,
            "responseBody": response_body,
        },
    }
