"""Generate fix recommendations based on error analysis."""

from __future__ import annotations

import re


def generate_fix_recommendation(processidentifier: str, errormessage: str, description: str, recordid: str = "") -> dict:
    """Generate a specific fix recommendation based on the error details.

    Args:
        processidentifier: The OmniScript process identifier.
        errormessage: The raw error message.
        description: Additional error description.
        recordid: The Salesforce record ID if available.

    Returns:
        dict: Contains 'fix_type', 'description', 'steps', and 'confidence'.
    """
    combined_text = f"{processidentifier} {errormessage} {description}".lower()

    # Check for CCSP payload validation errors
    if ("ccsp" in combined_text and
        ("invalid payload" in combined_text or "expected type" in combined_text) and
        ("found: null" in combined_text or "found null" in combined_text) and
        "filter" in combined_text):

        if "getexternalobjectdata" in processidentifier.lower():
            fix_description = "The GetExternalObjectData OmniScript is sending null filter values to CCSP, causing a 400 error."
            steps = [
                "Navigate to the GetExternalObjectData OmniScript in Salesforce Setup.",
                "Locate the Integration Procedure or HTTP Action that calls CCSP.",
                "Check the request body configuration for the filter structure.",
                f"Ensure the filter value is set to the record ID ({recordid}) instead of null.",
                "Update the filter mapping to use the input recordid parameter.",
                "Test the OmniScript with a valid record ID to verify the fix."
            ]
            return {
                "fix_type": "OMNISCRIPT_FILTER_FIX",
                "description": fix_description,
                "steps": steps,
                "confidence": 0.95,
                "affected_component": "GetExternalObjectData OmniScript"
            }

    # Generic payload validation error
    if "invalid payload" in combined_text and "expected type" in combined_text:
        fix_description = "The request payload contains null values where specific types are expected."
        steps = [
            "Review the API request payload structure.",
            "Identify fields with null values that should have valid data.",
            "Update the data mapping to provide appropriate values.",
            "Validate the payload against the API schema before sending."
        ]
        return {
            "fix_type": "PAYLOAD_VALIDATION_FIX",
            "description": fix_description,
            "steps": steps,
            "confidence": 0.8,
            "affected_component": "Request Payload"
        }

    # Default case
    return {
        "fix_type": "UNKNOWN",
        "description": "Unable to determine a specific fix. Manual investigation required.",
        "steps": ["Review error logs and system configuration.", "Consult documentation or support."],
        "confidence": 0.0,
        "affected_component": "Unknown"
    }