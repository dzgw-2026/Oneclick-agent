"""Parse Report Lambda — Action Group 1.

Extracts key fields from a One-Click Report row and identifies embedded
Salesforce record IDs in the error message for direct log lookup.
"""

from __future__ import annotations

import json
import re


# Patterns for Salesforce record IDs found in error messages
# Vlocity Error Log IDs: start with 'a9z' (VlocityErrorLog__c key prefix)
VLOCITY_ID_PATTERN = re.compile(r"\b(a9z[A-Za-z0-9]{12,15})\b")
# PS Exception Log IDs: start with 'a1W' (PS_Exception_Log__c key prefix)
EXCEPTION_ID_PATTERN = re.compile(r"\b(a1W[A-Za-z0-9]{12,15})\b")


def extract_salesforce_ids(errormessage: str) -> dict:
    """Extract Vlocity Error Log and PS Exception Log IDs from error message text."""
    vlocity_ids = list(set(VLOCITY_ID_PATTERN.findall(errormessage)))
    exception_ids = list(set(EXCEPTION_ID_PATTERN.findall(errormessage)))
    return {
        "vlocity_log_ids": vlocity_ids,
        "exception_log_ids": exception_ids,
    }


def parse_report(report: dict) -> dict:
    """Parse a single One-Click Report row into structured output."""
    user = report.get("user", "")
    datetime_str = report.get("datetime", "")
    processidentifier = report.get("processidentifier", "")
    errormessage = report.get("errormessage", "")
    description = report.get("description", "")

    ids = extract_salesforce_ids(errormessage)

    return {
        "user": user,
        "datetime": datetime_str,
        "processidentifier": processidentifier,
        "errormessage": errormessage,
        "description": description,
        "vlocity_log_ids": ids["vlocity_log_ids"],
        "exception_log_ids": ids["exception_log_ids"],
        "omniscript_name": processidentifier if processidentifier else "UNKNOWN",
        "has_direct_ids": bool(ids["vlocity_log_ids"] or ids["exception_log_ids"]),
    }


def handler(event, context):
    """Lambda handler for Bedrock Agent action group invocation."""
    # Bedrock Agent sends parameters in the action group event
    agent = event.get("agent", {})
    action_group = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    parameters = event.get("parameters", [])
    request_body = event.get("requestBody", {})

    # Extract report data from request body
    report_data = {}
    if request_body and "content" in request_body:
        content = request_body["content"]
        if "application/json" in content:
            properties = content["application/json"].get("properties", [])
            for prop in properties:
                report_data[prop["name"]] = prop["value"]

    parsed = parse_report(report_data)

    response_body = {"application/json": {"body": json.dumps(parsed)}}

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
