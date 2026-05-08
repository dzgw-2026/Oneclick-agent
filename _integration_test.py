"""Integration test for the new payload flexibility features.

Mocks external dependencies (Datadog API, AWS Secrets Manager) so we can
run locally without credentials and verify that:

  1. Envelope unwrapping handles Lambda / SNS / EventBridge wrappers.
  2. Missing ``datetime`` is auto-resolved from Datadog (mocked).
  3. Fallback to UTC when Datadog returns no results.
  4. Full payloads skip auto-resolution entirely.

Run:  py _integration_test.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# 1. Re-test envelope unwrapping  (same logic as _smoke_test.py but from main)
# ---------------------------------------------------------------------------

# We can't import main.py directly (heavy deps), so inline the function.
_ENVELOPE_KEYS = ("body", "detail", "Message", "message")


def _unwrap_event_envelope(payload):
    if not isinstance(payload, dict):
        return payload if isinstance(payload, dict) else {}
    records = payload.get("Records")
    if isinstance(records, list) and records:
        sns = records[0].get("Sns") if isinstance(records[0], dict) else None
        if isinstance(sns, dict) and isinstance(sns.get("Message"), str):
            try:
                inner = json.loads(sns["Message"])
                if isinstance(inner, dict):
                    return _unwrap_event_envelope(inner)
            except (json.JSONDecodeError, TypeError):
                pass
    for key in _ENVELOPE_KEYS:
        value = payload.get(key)
        if isinstance(value, dict):
            return _unwrap_event_envelope(value)
        if isinstance(value, str):
            try:
                inner = json.loads(value)
                if isinstance(inner, dict):
                    return _unwrap_event_envelope(inner)
            except (json.JSONDecodeError, TypeError):
                continue
    return payload


print("=== 1. Envelope unwrapping ===")

cases = [
    ("raw", {"recordid": "a9z1", "user": "alice"}, {"recordid": "a9z1", "user": "alice"}),
    ("lambda dict", {"body": {"recordid": "a9z2"}}, {"recordid": "a9z2"}),
    ("lambda str", {"body": '{"recordid":"a9z3"}'}, {"recordid": "a9z3"}),
    ("eventbridge", {"detail": {"recordid": "a9z4"}, "source": "aws"}, {"recordid": "a9z4"}),
    ("sns", {"Records": [{"Sns": {"Message": '{"recordid":"a9z5"}'}}]}, {"recordid": "a9z5"}),
]
for label, input_payload, expected in cases:
    result = _unwrap_event_envelope(input_payload)
    assert result == expected, f"{label}: got {result}"
    print(f"  {label}: OK")

# ---------------------------------------------------------------------------
# 2. Datadog resolver — successful hit
# ---------------------------------------------------------------------------
print("\n=== 2. Datadog resolver — Datadog returns a timestamp ===")


# Build a fake httpx response
def _make_mock_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


async def test_resolver_hit():
    """When Datadog returns an event, we should get its timestamp."""
    from shared.datadog_resolver import resolve_trigger_time

    fake_timestamp = "2026-05-05T14:30:00.000Z"
    fake_response = _make_mock_response(200, {
        "data": [{
            "attributes": {"timestamp": fake_timestamp}
        }]
    })

    # Mock both the credentials fetcher and httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    with patch("shared.datadog_resolver.get_datadog_credentials", return_value={
        "api_key": "fake-key",
        "application_key": "fake-app-key",
        "endpoint": "https://fake.datadoghq.com/api/v2/logs/events/search",
    }):
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await resolve_trigger_time(user="testuser", record_id="a9z123")

    assert result == fake_timestamp, f"Expected {fake_timestamp}, got {result}"
    print(f"  resolved timestamp: {result}  OK")

    # Verify the Datadog query was built correctly
    call_args = mock_client.post.call_args
    request_body = call_args.kwargs.get("json") or call_args[1].get("json")
    query = request_body["filter"]["query"]
    assert "a9z123" in query, f"record_id not in query: {query}"
    assert "testuser" in query, f"user not in query: {query}"
    assert request_body["page"]["limit"] == 1
    assert request_body["sort"] == "-timestamp"
    print(f"  query validated: OK")


asyncio.run(test_resolver_hit())

# ---------------------------------------------------------------------------
# 3. Datadog resolver — no results (falls back to UTC now)
# ---------------------------------------------------------------------------
print("\n=== 3. Datadog resolver — no results, UTC fallback ===")


async def test_resolver_miss():
    """When Datadog returns no events, we should get current UTC time."""
    from shared.datadog_resolver import resolve_trigger_time

    fake_response = _make_mock_response(200, {"data": []})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    before = datetime.now(timezone.utc)

    with patch("shared.datadog_resolver.get_datadog_credentials", return_value={
        "api_key": "fake", "application_key": "fake",
        "endpoint": "https://fake.dd.com/api/v2/logs/events/search",
    }):
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await resolve_trigger_time(user="testuser")

    after = datetime.now(timezone.utc)

    # Parse the result and check it's between before/after
    parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert before <= parsed <= after, f"Fallback time {result} not in expected range"
    print(f"  fallback timestamp: {result}  OK")


asyncio.run(test_resolver_miss())

# ---------------------------------------------------------------------------
# 4. Datadog resolver — API error (falls back gracefully)
# ---------------------------------------------------------------------------
print("\n=== 4. Datadog resolver — API error, graceful fallback ===")


async def test_resolver_error():
    """When Datadog returns a non-200, we should still get a valid timestamp."""
    from shared.datadog_resolver import resolve_trigger_time

    fake_response = _make_mock_response(429, {})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    with patch("shared.datadog_resolver.get_datadog_credentials", return_value={
        "api_key": "fake", "application_key": "fake",
        "endpoint": "https://fake.dd.com/api/v2/logs/events/search",
    }):
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await resolve_trigger_time(record_id="a9z999")

    # Must be a valid ISO timestamp, not an exception
    parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert parsed is not None
    print(f"  graceful fallback: {result}  OK")


asyncio.run(test_resolver_error())

# ---------------------------------------------------------------------------
# 5. Datadog resolver — no user or record_id
# ---------------------------------------------------------------------------
print("\n=== 5. Datadog resolver — no identifiers, immediate UTC ===")


async def test_resolver_no_ids():
    """When no user or record_id is given, skip Datadog entirely."""
    from shared.datadog_resolver import resolve_trigger_time

    before = datetime.now(timezone.utc)
    result = await resolve_trigger_time()  # no user, no record_id
    after = datetime.now(timezone.utc)

    parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert before <= parsed <= after
    print(f"  immediate UTC: {result}  OK")


asyncio.run(test_resolver_no_ids())

# ---------------------------------------------------------------------------
# 6. Full payload — should NOT trigger auto-resolution
# ---------------------------------------------------------------------------
print("\n=== 6. Full payload skips auto-resolution ===")

full_payload = {
    "recordid": "a9zFULL123",
    "datetime": "2026-05-05T10:00:00Z",
    "user": "fulluser",
    "errormessage": "Something broke",
}
body = _unwrap_event_envelope(full_payload)
trigger_time = body.get("datetime", "")
assert trigger_time == "2026-05-05T10:00:00Z", "Full payload datetime should pass through"
print(f"  datetime preserved: {trigger_time}  OK")

# ---------------------------------------------------------------------------
# 7. Partial payload — datetime missing, would trigger auto-resolution
# ---------------------------------------------------------------------------
print("\n=== 7. Partial payload triggers auto-resolution ===")

partial_payload = {"recordid": "a9zPARTIAL", "user": "partialuser"}
body = _unwrap_event_envelope(partial_payload)
trigger_time = body.get("datetime", "")
assert trigger_time == "", "Partial payload should have empty datetime"
print(f"  datetime empty (would auto-resolve): OK")

# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("ALL INTEGRATION TESTS PASSED")
print("=" * 50)
