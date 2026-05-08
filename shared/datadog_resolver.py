"""Datadog-based trigger time resolver.

When a One-Click report payload arrives without a ``datetime`` field, this
module queries Datadog for the most recent matching event (by ``record_id``
and/or ``user``) and returns its timestamp as ISO 8601. If Datadog returns
no hit or fails, the current UTC time is used as a fallback.

Used by :func:`main.invoke` to support flexible/event-driven payloads where
upstream systems may not include the trigger time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.datadog_credentials import get_datadog_credentials


log = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def resolve_trigger_time(
    user: str = "",
    record_id: str = "",
    lookback_minutes: int = 60,
) -> str:
    """Resolve a trigger timestamp from Datadog.

    Searches for the most recent Vlocity error-log CDC event matching the
    provided ``user`` (LAN ID alias) and/or ``record_id``. Returns the
    event timestamp as an ISO 8601 string. Falls back to the current UTC
    time if no event is found or the call fails.

    Args:
        user: Agent LAN ID / alias to match on. Optional.
        record_id: Salesforce record ID to match on. Optional.
        lookback_minutes: How far back to search (default 60).

    Returns:
        ISO 8601 timestamp string. Never raises.
    """
    if not user and not record_id:
        log.info("resolve_trigger_time- no user or record_id; using UTC now")
        return _utc_now_iso()

    try:
        import httpx

        credentials = get_datadog_credentials()
        api_key = credentials['api_key']
        app_key = credentials['application_key']
        endpoint = credentials['endpoint']

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(minutes=lookback_minutes)

        # Build a narrow query: prefer record_id when available, else user alias.
        query_parts = [
            "env_type:production",
            "@data.payload.ChangeEventHeader.entityName:"
            "vlocity_cmt__VlocityErrorLogEntry__c",
        ]
        if record_id:
            query_parts.append(f"@data.payload.Id:{record_id}")
        if user:
            query_parts.append(f"@user_role.alias:{user}")

        request_body = {
            'filter': {
                'from': start_dt.isoformat(),
                'to': end_dt.isoformat(),
                'query': " ".join(query_parts),
            },
            # Most recent first so we can take the first hit.
            'sort': '-timestamp',
            'page': {'limit': 1},
        }
        headers = {
            'DD-API-KEY': api_key,
            'DD-APPLICATION-KEY': app_key,
            'Content-Type': 'application/json',
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, headers=headers, json=request_body)

        if response.status_code != 200:
            log.warning(
                "resolve_trigger_time- Datadog returned %s; falling back to UTC now",
                response.status_code,
            )
            return _utc_now_iso()

        events = response.json().get('data', [])
        if not events:
            log.info("resolve_trigger_time- no Datadog match; using UTC now")
            return _utc_now_iso()

        timestamp = (
            events[0].get('attributes', {}).get('timestamp')
            or events[0].get('attributes', {}).get('attributes', {}).get('timestamp')
        )
        if not timestamp:
            log.info("resolve_trigger_time- event missing timestamp; using UTC now")
            return _utc_now_iso()

        log.info(f"resolve_trigger_time- resolved from Datadog: {timestamp}")
        return _normalize_iso(timestamp)

    except Exception as e:
        log.error(f"resolve_trigger_time- error, using UTC now: {e}")
        return _utc_now_iso()


def _normalize_iso(value: str) -> str:
    """Ensure the timestamp is a valid ISO 8601 string.

    Datadog returns timestamps in formats like ``2026-04-27T17:06:40.123Z``.
    Some downstream code uses ``datetime.fromisoformat`` which (pre-3.11) does
    not accept the trailing ``Z``. We normalize defensively.
    """
    try:
        # If it already parses, leave it alone.
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
    except Exception:
        return _utc_now_iso()
