"""Query PS Exception Logs — lookup by ID or search by application/location."""

from __future__ import annotations

from shared.sf_client import (
    get_exception_log_by_id as _get_by_id,
    search_exception_logs as _search,
)


def get_exception_log_by_id(log_id: str) -> dict:
    """Look up a PS Exception Log by its Salesforce record ID."""
    log = _get_by_id(log_id)
    if log:
        return {"exceptions": [log], "count": 1}
    return {"exceptions": [], "count": 0}


def search_exception_logs(application: str = "", location: str = "") -> dict:
    """Search PS Exception Logs by application and/or exception location."""
    logs = _search(application=application, location=location)
    return {"exceptions": logs, "count": len(logs)}
