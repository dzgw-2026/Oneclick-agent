"""Query Vlocity Logs Lambda — Action Group 2.

Looks up Vlocity Error Logs by direct ID or by agent LAN ID + timeframe.
Parses HTTP request/response payloads to extract structured error details.
"""

from __future__ import annotations

import json
import os
import sys

# Add shared layer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from sf_client import get_vlocity_log_by_id, search_vlocity_logs


def parse_http_payload(raw: str) -> dict:
    """Attempt to parse an HTTP request/response string as JSON."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw}


def enrich_log(log: dict) -> dict:
    """Parse HTTP payloads and extract key error fields from a Vlocity log."""
    request_data = parse_http_payload(log.get("HTTPRequest", ""))
    response_data = parse_http_payload(log.get("HTTPResponse", ""))

    error_details = ""
    if isinstance(response_data, dict):
        # Extract nested error messages
        details = response_data.get("details", {})
        if isinstance(details, dict):
            # Check for field order errors
            field_orders = details.get("fieldorders", [])
            if field_orders and isinstance(field_orders, list):
                for fo in field_orders:
                    resp = fo.get("response", {})
                    if resp.get("message"):
                        error_details = resp["message"]
            # Check for nested service agreement errors
            sa = details.get("serviceAgreements", {})
            if isinstance(sa, dict) and sa.get("message"):
                error_details = sa["message"]
            # Check for direct message
            if details.get("message"):
                error_details = details["message"]
        if response_data.get("message"):
            error_details = response_data["message"]

    return {
        "Id": log.get("Id", ""),
        "Name": log.get("Name", ""),
        "ErrorCode": log.get("ErrorCode", ""),
        "Functionality": log.get("Functionality", ""),
        "Status": log.get("Status", ""),
        "ContextId": log.get("ContextId", ""),
        "SourceName": log.get("SourceName", ""),
        "User": log.get("User", ""),
        "Datetime": log.get("Datetime", ""),
        "ProcessIdentifier": log.get("ProcessIdentifier", ""),
        "request_data": request_data,
        "response_data": response_data,
        "response_code": str(response_data.get("code", "")),
        "response_status": str(response_data.get("status", "")),
        "response_integration": str(response_data.get("integration", "")),
        "error_details": error_details,
        "exception_log_id": log.get("ExceptionLogId"),
    }


def handler(event, context):
    """Lambda handler for Bedrock Agent action group invocation."""
    action_group = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    parameters = event.get("parameters", [])

    # Extract parameters
    params = {p["name"]: p["value"] for p in parameters}

    results = []

    if api_path == "/query-by-id":
        log_id = params.get("log_id", "")
        if log_id:
            log = get_vlocity_log_by_id(log_id)
            if log:
                results.append(enrich_log(log))

    elif api_path == "/search":
        user = params.get("user", "")
        start_time = params.get("start_time", "")
        end_time = params.get("end_time", "")
        if user and start_time and end_time:
            logs = search_vlocity_logs(user, start_time, end_time)
            results = [enrich_log(log) for log in logs]

    response_body = {
        "application/json": {
            "body": json.dumps({"logs": results, "count": len(results)})
        }
    }

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": "GET",
            "httpStatusCode": 200,
            "responseBody": response_body,
        },
    }
