"""Query Vlocity Error Logs — lookup by ID or search by user + timeframe."""

from __future__ import annotations

import json

from shared.sf_client import (
    get_vlocity_log_by_id as _get_by_id,
    search_vlocity_logs as _search,
)


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
        details = response_data.get("details", {})
        if isinstance(details, dict):
            field_orders = details.get("fieldorders", [])
            if field_orders and isinstance(field_orders, list):
                for fo in field_orders:
                    resp = fo.get("response", {})
                    if resp.get("message"):
                        error_details = resp["message"]
            sa = details.get("serviceAgreements", {})
            if isinstance(sa, dict) and sa.get("message"):
                error_details = sa["message"]
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


def get_vlocity_log_by_id(log_id: str) -> dict:
    """Look up a single Vlocity Error Log by Salesforce ID and return enriched data."""
    log = _get_by_id(log_id)
    if log:
        return {"logs": [enrich_log(log)], "count": 1}
    return {"logs": [], "count": 0}


def search_vlocity_logs(user: str, start_time: str, end_time: str) -> dict:
    """Search Vlocity Error Logs by agent LAN ID and time range."""
    logs = _search(user, start_time, end_time)
    enriched = [enrich_log(log) for log in logs]
    return {"logs": enriched, "count": len(enriched)}
