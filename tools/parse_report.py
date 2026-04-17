"""Parse One-Click Report — extract structured data and Salesforce IDs."""

from __future__ import annotations

import re

VLOCITY_ID_PATTERN = re.compile(r"\b(a9z[A-Za-z0-9]{12,15})\b")
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
