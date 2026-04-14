"""Query Exception Logs Lambda — Action Group 3.

Looks up PS Exception Logs by Salesforce ID and returns exception details
including application, location, type, severity, and error message.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from sf_client import get_exception_log_by_id, search_exception_logs


def handler(event, context):
    """Lambda handler for Bedrock Agent action group invocation."""
    action_group = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    parameters = event.get("parameters", [])

    params = {p["name"]: p["value"] for p in parameters}

    results = []

    if api_path == "/query-by-id":
        log_id = params.get("log_id", "")
        if log_id:
            log = get_exception_log_by_id(log_id)
            if log:
                results.append(log)

    elif api_path == "/search":
        application = params.get("application", "")
        location = params.get("location", "")
        logs = search_exception_logs(application=application, location=location)
        results = logs

    response_body = {
        "application/json": {
            "body": json.dumps({"exceptions": results, "count": len(results)})
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
