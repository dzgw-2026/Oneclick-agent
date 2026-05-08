"""One-Click Report Analysis Agent — Strands on AgentCore Runtime.

Defines the agent with @tool-decorated functions for report parsing,
log lookups, and issue classification. Deployed on AgentCore Runtime.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional
import boto3
from botocore.exceptions import ClientError

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from tools.parse_report import parse_report as _parse_report
from tools.classify_issue import classify_issue as _classify_issue
from tools.query_vlocity_logs import (
    get_vlocity_log_by_id as _get_vlocity_log,
    search_vlocity_logs as _search_vlocity,
)
from tools.query_exception_logs import (
    get_exception_log_by_id as _get_exception_log,
    search_exception_logs as _search_exceptions,
)
from tools.query_mulesoft_logs import query_mulesoft_logs
from shared.dynamodb_writer import save_analysis_result
from shared.s3_writer import save_oneclick_artifacts


app = BedrockAgentCoreApp()
log = app.logger


# ---------------------------------------------------------------------------
# Datadog Credentials Management
# ---------------------------------------------------------------------------
# Credentials handling lives in shared/datadog_credentials.py so other shared
# modules (e.g. the datetime resolver) can reuse the same cached credentials
# without introducing a circular import on main.py.

from shared.datadog_credentials import get_datadog_credentials  # noqa: E402


# ---------------------------------------------------------------------------
# Tools — @tool wrappers around the module implementations
# ---------------------------------------------------------------------------

@tool
def parse_report(
    user: str,
    datetime: str = "",
    processidentifier: str = "",
    errormessage: str = "",
    description: str = "",
) -> dict:
    """Parse a One-Click Report to extract structured data and identify
    embedded Salesforce record IDs (Vlocity Error Log IDs starting with
    'a9z' and PS Exception Log IDs starting with 'a1W').

    Args:
        user: Agent LAN ID.
        datetime: Report timestamp (ISO 8601).
        processidentifier: OmniScript process identifier.
        errormessage: Raw error message text.
        description: Agent-entered description of the issue.
    """
    log.info("_parse_report- Start...")

    return _parse_report({
        "user": user,
        "datetime": datetime,
        "processidentifier": processidentifier,
        "errormessage": errormessage,
        "description": description,
    })


@tool
def get_vlocity_log_by_id(log_id: str) -> dict:
    """Look up a Vlocity Error Log by its Salesforce record ID. Returns the
    full log including HTTP request/response payloads with parsed error details.

    Args:
        log_id: Salesforce Vlocity Error Log ID (starts with 'a9z').
    """
    log.info("get_vlocity_log_by_id- Start...")

    return _get_vlocity_log(log_id)


@tool
def search_vlocity_logs(user: str, start_time: str, end_time: str) -> dict:
    """Search for Vlocity Error Logs by agent LAN ID and time range. Use when
    no direct log IDs are available in the report. Search +/- 30 minutes around
    the report timestamp.

    Args:
        user: Agent LAN ID.
        start_time: Start of time window (ISO 8601).
        end_time: End of time window (ISO 8601).
    """
    log.info("search_vlocity_logs- Start...")

    return _search_vlocity(user, start_time, end_time)


@tool
def get_exception_log_by_id(log_id: str) -> dict:
    """Look up a PS Exception Log by its Salesforce record ID. Returns
    exception type, severity, location, and error message.

    Args:
        log_id: Salesforce PS Exception Log ID (starts with 'a1W').
    """
    log.info("get_exception_log_by_id- Start...")

    return _get_exception_log(log_id)


@tool
def search_exception_logs(application: str = "", location: str = "") -> dict:
    """Search PS Exception Logs by application name and/or exception location
    (class name). Use to find related exceptions when you know the application
    or error location.

    Args:
        application: Application name (e.g., 'CCSP').
        location: Exception location / class name (e.g., 'CCSP_IP_GetRatesFlyoutInfo').
    """
    log.info("search_exception_logs- Start...")

    return _search_exceptions(application=application, location=location)


@tool
def classify_issue(description: str, error_data: str = "") -> dict:
    """Classify an issue based on the agent's description text and any error
    data gathered from log lookups. Returns category (LATENCY, UI_ERROR,
    AUTH_ERROR, DATA_ERROR, UNKNOWN), confidence score, and whether recording
    review is needed.

    Args:
        description: Agent-entered description of the issue.
        error_data: Error data gathered from log lookups (optional).
    """
    log.info("classify_issue- Start...")

    return _classify_issue(description, error_data)


@tool
async def query_datadog_error_logs(record_id: str, user: str = "", trigger_time: str = "", lookback_minutes: int = 1440) -> dict:
    """Query Datadog for Vlocity error log entries filtered by user LAN ID.
    Filters for error status codes only (non-200). Returns the full error log
    payload including HTTP request/response, error code, functionality, and
    user details from the Datadog CDC event stream.

    When error_message is empty in the input data, use lookback_minutes=10.
    Otherwise, the default of 1440 minutes (24 hours) is appropriate.

    Args:
        record_id: Salesforce Vlocity Error Log record ID (starts with 'a9z').
        user: Agent LAN ID / alias (required to narrow results).
        trigger_time: Trigger timestamp (ISO 8601 format).
        lookback_minutes: Minutes to look back from trigger time (default: 1440).
    """
    log.info("query_datadog_error_logs- Start...")

    try:
        trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00')) if trigger_time else datetime.now()
    except ValueError:
        trigger_dt = datetime.now()
        log.info("query_datadog_error_logs- error...")
    return await _fetch_datadog_logs(
        user=user,
        record_id=record_id,
        trigger_dt=trigger_dt,
        lookback_minutes=lookback_minutes,
    )


# ---------------------------------------------------------------------------
# Tools — persistence and supplementary data
# ---------------------------------------------------------------------------

@tool
async def fetch_datadog_session_logs(user: str, record_id: str, trigger_time: str) -> dict:
    """Fetch the last 10 minutes of Datadog error logs for a user session.
    Always call this in addition to query_datadog_error_logs to capture the
    user's recent activity window around the trigger time.

    Args:
        user: Agent LAN ID.
        record_id: Salesforce Vlocity Error Log record ID.
        trigger_time: Trigger timestamp (ISO 8601 format).
    """
    log.info("fetch_datadog_session_logs- Start...")

    try:
        trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00')) if trigger_time else datetime.now()
    except ValueError:
        trigger_dt = datetime.now()
        log.info("fetch_datadog_session_logs- error...")
    return await _fetch_datadog_logs(
        user=user,
        record_id=record_id,
        trigger_dt=trigger_dt,
        lookback_minutes=10,
    )


@tool
async def fetch_mulesoft_logs(ctx_id: str, trigger_time: str) -> dict:
    """Fetch Mulesoft debug logs from Datadog using a correlation/context ID
    (also called Pivot ID). The ctx_id should be extracted from Datadog error
    log entries via the 'context_id' field. If that field contains colons
    (e.g. '2026-04-27T17:06:40:8ee3825a...'), use only the last colon-separated
    segment. The ctx_id can also be extracted from the error_message field by
    looking for patterns like 'CtxId:<id>' or 'ContextId: <id>'.

    Args:
        ctx_id: Correlation/context ID (Pivot ID) from a Vlocity error log.
        trigger_time: Trigger timestamp (ISO 8601 format).
    """
    log.info("fetch_mulesoft_logs- Start...")

    try:
        credentials = get_datadog_credentials()
        return await query_mulesoft_logs(
            ctx_id=ctx_id,
            trigger_time=trigger_time,
            credentials=credentials,
        )
    except Exception as e:
        log.error(f"Failed to fetch Mulesoft logs: {e}")
        log.info("fetch_mulesoft_logs- error...")
        return {"success": False, "error": str(e), "ctx_id": ctx_id}


@tool
async def save_to_dynamodb(
    user: str,
    trigger_time: str,
    record_id: str,
    error_message: str,
    root_cause: str,
    error_code: str = "",
    mulesoft_logs: str = "",
) -> dict:
    """Save the completed root cause analysis to DynamoDB. Call this after
    producing the full root cause analysis. Failures are reported but must
    never interrupt the analysis response to the caller.

    Args:
        user: Agent LAN ID.
        trigger_time: Trigger timestamp (ISO 8601).
        record_id: Salesforce record ID.
        error_message: Original error message from the input.
        root_cause: Root cause analysis result as a JSON string or plain text.
        error_code: Extracted HTTP/application error code (optional).
        mulesoft_logs: Mulesoft logs as a JSON string (optional).
    """
    log.info("save_to_dynamodb- Start...")

    try:
        mulesoft_data: Any = json.loads(mulesoft_logs) if mulesoft_logs else None
    except (json.JSONDecodeError, TypeError):
        mulesoft_data = None

    try:
        root_cause_data: Any = json.loads(root_cause) if root_cause else {}
    except (json.JSONDecodeError, TypeError):
        root_cause_data = {"raw_text": root_cause} if root_cause else {}

    if mulesoft_data and mulesoft_data.get('success'):
        root_cause_data['mulesoft_correlation'] = {
            'ctx_id': mulesoft_data.get('ctx_id'),
            'log_count': len(mulesoft_data.get('logs', [])),
        }

    try:
        result = await save_analysis_result(
            user=user,
            datetime_str=trigger_time,
            record_id=record_id,
            error_message=error_message,
            root_cause=root_cause_data,
            error_code=error_code,
            mulesoft_logs=mulesoft_data,
        )
        if result.get("success"):
            log.info("Persisted analysis result to DynamoDB: %s", result.get("key"))
        else:
            log.error("Failed to persist analysis result: %s", result.get("error"))
        return result
    except Exception as e:
        log.error(f"Unexpected error saving to DynamoDB: {e}")
        log.info("save_to_dynamodb- error...")
        return {"success": False, "error": str(e)}


@tool
async def save_to_s3(
    record_id: str,
    user: str,
    trigger_time: str,
    raw_data: str = "",
    session_log_data: str = "",
    mulesoft_logs: str = "",
    analysis_results: str = "",
) -> dict:
    """Save One-Click analysis artifacts to S3. Call this after completing
    analysis with the data gathered during the investigation. Failures are
    reported but must never interrupt the analysis response to the caller.

    Args:
        record_id: Salesforce record ID.
        user: Agent LAN ID.
        trigger_time: Trigger timestamp (ISO 8601).
        raw_data: Primary Datadog error logs as a JSON string.
        session_log_data: Session Datadog logs (10-min window) as a JSON string.
        mulesoft_logs: Mulesoft logs as a JSON string.
        analysis_results: Analysis results as a JSON string or plain text.
    """
    log.info("save_to_s3- Start...")

    def _parse_json(s: str) -> Any:
        if not s:
            return None
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return {"raw": s}

    try:
        result = await save_oneclick_artifacts(
            record_id=record_id,
            user=user,
            datetime_str=trigger_time,
            raw_data=_parse_json(raw_data),
            session_log_data=_parse_json(session_log_data),
            mulesoft_logs=_parse_json(mulesoft_logs),
            analysis_results=_parse_json(analysis_results),
        )
        if result.get("success"):
            log.info(
                "Persisted One-Click artifacts to S3 bucket=%s prefix=%s keys=%s",
                result.get("bucket"),
                result.get("prefix"),
                result.get("keys"),
            )
        else:
            log.error("Failed to persist S3 artifacts: %s", result.get("error"))
        return result
    except Exception as e:
        log.error(f"Unexpected error saving to S3: {e}")
        log.info("save_to_s3- error...")
        return {"success": False, "error": str(e)}


@tool
async def persist_analysis_artifacts(
    user: str,
    trigger_time: str,
    record_id: str,
    error_message: str,
    analysis_results: str,
    raw_report_data: str = "",
    mulesoft_logs: str = "",
    ctx_id: str = "",
) -> dict:
    """Persist the completed analysis and supporting artifacts.

    This tool is intended to be called by the agent after it has finished
    the root cause analysis. It gathers the Datadog data needed for
    persistence, derives the error code, then writes to DynamoDB and S3.

    Args:
        user: Agent LAN ID.
        trigger_time: Trigger timestamp (ISO 8601).
        record_id: Salesforce record ID.
        error_message: Original error message from the input.
        analysis_results: Final analysis as a JSON string or plain text.
        raw_report_data: Original input payload as a JSON string.
        mulesoft_logs: Mulesoft logs as JSON string. If omitted, the tool
            will attempt to fetch logs using a derived context ID.
        ctx_id: Optional Mulesoft context/correlation ID.
    """
    log.info("persist_analysis_artifacts- Start...")

    analysis_obj = _safe_parse_json(analysis_results)

    try:
        raw_payload: Any = json.loads(raw_report_data) if raw_report_data else {
            "recordid": record_id,
            "datetime": trigger_time,
            "user": user,
            "errormessage": error_message,
        }
    except (json.JSONDecodeError, TypeError):
        raw_payload = {"raw": raw_report_data}

    try:
        trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00')) if trigger_time else datetime.now()
    except ValueError:
        trigger_dt = datetime.now()

    lookback_for_raw = 10 if not error_message else 1440
    raw_logs = await _fetch_datadog_logs(
        user=user,
        record_id=record_id,
        trigger_dt=trigger_dt,
        lookback_minutes=lookback_for_raw,
    )
    session_logs = await _fetch_datadog_logs(
        user=user,
        record_id=record_id,
        trigger_dt=trigger_dt,
        lookback_minutes=10,
    )

    error_code = _extract_error_code(analysis_obj, raw_logs)

    resolved_ctx_id = _derive_ctx_id(
        explicit_ctx_id=ctx_id,
        analysis_obj=analysis_obj,
        raw_payload=raw_payload,
        raw_logs=raw_logs,
        error_message=error_message,
    )
    mulesoft_data = await _resolve_mulesoft_logs(
        trigger_time=trigger_time,
        mulesoft_logs=mulesoft_logs,
        resolved_ctx_id=resolved_ctx_id,
    )

    ddb_result = await save_analysis_result(
        user=user,
        datetime_str=trigger_time,
        record_id=record_id,
        error_message=error_message,
        root_cause=analysis_obj,
        error_code=error_code,
        mulesoft_logs=mulesoft_data,
    )
    s3_result = await save_oneclick_artifacts(
        record_id=record_id,
        user=user,
        datetime_str=trigger_time,
        raw_data=raw_payload,
        session_log_data=session_logs,
        mulesoft_logs=mulesoft_data,
        analysis_results=analysis_obj,
    )

    if ddb_result.get("success"):
        log.info("persist_analysis_artifacts- DynamoDB save succeeded")
    else:
        log.error("persist_analysis_artifacts- DynamoDB save failed: %s", ddb_result.get("error"))

    if s3_result.get("success"):
        log.info("persist_analysis_artifacts- S3 save succeeded")
    else:
        log.error("persist_analysis_artifacts- S3 save failed: %s", s3_result.get("error"))

    return {
        "success": ddb_result.get("success") and s3_result.get("success"),
        "dynamodb": ddb_result,
        "s3": s3_result,
        "error_code": error_code,
        "ctx_id": resolved_ctx_id,
        "mulesoft_included": bool(mulesoft_data),
    }


def _normalize_ctx_id(value: str) -> str:
    if not value:
        return ""
    candidate = str(value).strip()
    if not candidate:
        return ""
    # Datadog can emit context IDs prefixed by timestamp segments.
    if ":" in candidate:
        candidate = candidate.split(":")[-1].strip()
    return candidate


def _extract_ctx_id_from_error_message(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"(?:CtxId|ContextId)\s*[:=]\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
    if match:
        return _normalize_ctx_id(match.group(1))
    return ""


def _extract_ctx_id_from_raw_logs(raw_logs: Optional[dict]) -> str:
    if not raw_logs or not raw_logs.get("success"):
        return ""
    for log_item in raw_logs.get("error_logs", []):
        ctx_value = _normalize_ctx_id((log_item or {}).get("context_id", ""))
        if ctx_value:
            return ctx_value
    return ""


def _derive_ctx_id(
    explicit_ctx_id: str,
    analysis_obj: dict,
    raw_payload: Any,
    raw_logs: Optional[dict],
    error_message: str,
) -> str:
    candidates: list[str] = []

    candidates.append(explicit_ctx_id)
    for key in ("ctx_id", "context_id", "pivot_id", "mulesoft_ctx_id"):
        candidates.append(str(analysis_obj.get(key, "")))

    if isinstance(raw_payload, dict):
        for key in ("ctx_id", "context_id", "pivot_id"):
            candidates.append(str(raw_payload.get(key, "")))
        candidates.append(_extract_ctx_id_from_error_message(str(raw_payload.get("errormessage", ""))))

    candidates.append(_extract_ctx_id_from_error_message(error_message))
    candidates.append(_extract_ctx_id_from_raw_logs(raw_logs))

    for candidate in candidates:
        normalized = _normalize_ctx_id(candidate)
        if normalized:
            return normalized
    return ""


async def _resolve_mulesoft_logs(
    trigger_time: str,
    mulesoft_logs: str,
    resolved_ctx_id: str,
) -> Optional[dict]:
    if mulesoft_logs:
        try:
            parsed = json.loads(mulesoft_logs)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"raw": mulesoft_logs}

    if not resolved_ctx_id:
        return None

    try:
        credentials = get_datadog_credentials()
        data = await query_mulesoft_logs(
            ctx_id=resolved_ctx_id,
            trigger_time=trigger_time,
            credentials=credentials,
        )
        if isinstance(data, dict):
            return data
        return {"raw": data, "ctx_id": resolved_ctx_id}
    except Exception as e:
        log.error(f"persist_analysis_artifacts- Failed to fetch Mulesoft logs: {e}")
        return {"success": False, "error": str(e), "ctx_id": resolved_ctx_id}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH) as f:
        return f.read()


def _safe_parse_json(text: str) -> dict:
    """Best-effort parse for agent output that may be JSON or plain text."""
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"analysis_text": text}


def _extract_error_code(analysis_obj: dict, raw_logs: Optional[dict]) -> str:
    """Prefer Datadog-derived error code, then fall back to analysis payload."""
    if raw_logs and raw_logs.get("success"):
        logs = raw_logs.get("error_logs", [])
        if logs:
            first = logs[0] or {}
            code = first.get("error_code")
            if code:
                return str(code)

    for key in ("error_code", "ErrorCode", "code"):
        value = analysis_obj.get(key)
        if value:
            return str(value)

    return ""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    parse_report,
    get_vlocity_log_by_id,
    search_vlocity_logs,
    get_exception_log_by_id,
    search_exception_logs,
    classify_issue,
    query_datadog_error_logs,
    fetch_datadog_session_logs,
    fetch_mulesoft_logs,
    save_to_dynamodb,
    save_to_s3,
    persist_analysis_artifacts,
]

_agent = None


def get_or_create_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            model=load_model(),
            system_prompt=_load_system_prompt(),
            tools=ALL_TOOLS,
        )
    return _agent


# ---------------------------------------------------------------------------
# Datadog fetch helper
# ---------------------------------------------------------------------------

_DD_ERROR_CODES = [
    300, 301, 302, 303, 304, 305, 306, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426, 427, 428, 429, 431, 440, 444, 449, 450, 451, 460, 463, 494, 495, 496, 497, 498, 499,
    500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 520, 521, 522, 523, 524, 525, 526, 527, 530, 561, 598, 599
]

#_DD_ERROR_CODES = [400, 401, 403, 404, 405, 408, 422, 500, 503]



async def _fetch_datadog_logs(
    user: str,
    record_id: str,
    trigger_dt: datetime,
    lookback_minutes: int,
) -> dict:
    """Query Datadog for Vlocity error log events filtered by LAN ID.

    Returns the same dict shape previously produced inline in ``invoke()``.
    Never raises; failures are returned as ``{"success": False, ...}``.
    """
    try:
        import httpx

        credentials = get_datadog_credentials()
        api_key = credentials['api_key']
        app_key = credentials['application_key']
        endpoint = credentials['endpoint']

        start_dt = trigger_dt - timedelta(minutes=lookback_minutes)
        headers = {
            'DD-API-KEY': api_key,
            'DD-APPLICATION-KEY': app_key,
            'Content-Type': 'application/json',
        }

        matched_logs: list[dict] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []
            for code in _DD_ERROR_CODES:
                query = (
                    "env_type:production "
                    "@data.payload.ChangeEventHeader.entityName:"
                    "vlocity_cmt__VlocityErrorLogEntry__c "
                    f"@data.payload.vlocity_cmt__ErrorCode__c:{code}"
                )
                request_body = {
                    'filter': {
                        'from': start_dt.isoformat(),
                        'to': trigger_dt.isoformat(),
                        'query': query,
                    },
                    'sort': 'timestamp',
                    'page': {'limit': 100},
                }
                tasks.append(client.post(endpoint, headers=headers, json=request_body))

            # Batch execution to avoid 429s (especially with the large _DD_ERROR_CODES list)
            responses = []
            chunk_size = 5
            for i in range(0, len(tasks), chunk_size):
                chunk = tasks[i:i + chunk_size]
                chunk_responses = await asyncio.gather(*chunk, return_exceptions=True)
                responses.extend(chunk_responses)
                if i + chunk_size < len(tasks):
                    await asyncio.sleep(0.4)

            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    log.error(f"Helper fetch failed for code index {i}: {response}")
                    continue
                
                if response.status_code == 429:
                    log.warning(f"Helper fetch hit 429 for code index {i}")
                    continue

                try:
                    response.raise_for_status()
                    data = response.json()
                    events = data.get('data', [])
                except Exception as e:
                    log.error(f"Helper parse failed for code index {i}: {e}")
                    continue

                for event in events:
                    attrs = event.get('attributes', {}).get('attributes', {})
                    user_role = attrs.get('user_role', {})
                    user_alias = user_role.get('alias', '')

                    # Filter by LAN ID when provided.
                    if user and user_alias != user:
                        continue

                    dd_payload = attrs.get('data', {}).get('payload', {})

                    http_response = dd_payload.get('CCSP_HTTPResponse__c', '')
                    parsed_response: Any = {}
                    if http_response:
                        try:
                            parsed_response = json.loads(http_response)
                        except (json.JSONDecodeError, TypeError):
                            parsed_response = {'raw': http_response}

                    user_profile = attrs.get('user_profile', {})

                    matched_logs.append({
                        'record_id': record_id,
                        'lan_id': user_alias,
                        'name': dd_payload.get('Name', ''),
                        'error_code': str(dd_payload.get('vlocity_cmt__ErrorCode__c', '')),
                        'functionality': dd_payload.get('CCSP_Functionality__c', ''),
                        'callout_status': dd_payload.get('CCSP_CalloutStatus__c', ''),
                        'log_number': dd_payload.get('CCSP_LogNumber__c', ''),
                        'object_name': dd_payload.get('vlocity_cmt__ObjectName__c', ''),
                        'status': dd_payload.get('CCSP_Status__c', ''),
                        'context_id': dd_payload.get('vlocity_cmt__ContextId__c', ''),
                        'created_date': dd_payload.get('CreatedDate', ''),
                        'http_request': dd_payload.get('CCSP_HTTPRequest__c', ''),
                        'http_response': parsed_response,
                        'user_name': user_profile.get('name', ''),
                        'user_alias': user_alias,
                        'user_role_name': user_role.get('role_name', ''),
                        'timestamp': event.get('attributes', {}).get('timestamp', ''),
                    })

        log.info(
            f"Datadog: {len(matched_logs)} logs for user={user} record_id={record_id} "
            f"lookback_minutes={lookback_minutes}"
        )
        return {
            'success': True,
            'record_id': record_id,
            'match_count': len(matched_logs),
            'error_logs': matched_logs,
            'time_range': {
                'start': start_dt.isoformat(),
                'end': trigger_dt.isoformat(),
            },
        }
    except Exception as e:
        log.error(f"Error fetching Datadog logs: {e}")
        return {
            'success': False,
            'error': str(e),
            'record_id': record_id,
        }


# ---------------------------------------------------------------------------
# AgentCore Runtime entrypoint
# ---------------------------------------------------------------------------

# Common envelope keys used by upstream event sources. The first matching key
# whose value is a dict (or JSON-decodable string for SNS) is treated as the
# inner report body. This lets the same HTTP entrypoint accept:
#   - Raw JSON         : { "recordid": "...", ... }
#   - Lambda proxy     : { "body": { ... } } or { "body": "<json string>" }
#   - SNS notification : { "Records": [ { "Sns": { "Message": "<json>" } } ] }
#   - EventBridge rule : { "detail": { ... } }
_ENVELOPE_KEYS = ("body", "detail", "Message", "message")


def _unwrap_event_envelope(payload: Any) -> dict:
    """Strip well-known event-source envelopes to reach the report body.

    Returns ``payload`` unchanged when no recognized envelope is detected.
    Always returns a dict; if extraction yields a non-dict (or fails), the
    original payload is returned so downstream ``.get()`` calls still work.
    """
    if not isinstance(payload, dict):
        return payload if isinstance(payload, dict) else {}

    # SNS via Lambda: { "Records": [ { "Sns": { "Message": "<json>" } } ] }
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


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint. Receives report data and streams analysis.

    Accepts both fully-populated payloads and partial/event-driven payloads.
    Missing fields are auto-resolved so upstream callers (e.g. monitoring
    webhooks, EventBridge rules, SNS subscriptions) only need to supply
    enough identifying information for the agent to proceed.
    """
    log.info("Invoking One-Click Analysis Agent...")
    log.info(f"System prompt path: {_SYSTEM_PROMPT_PATH}")

    # Unwrap any recognized event-source envelope to reach the report body.
    body = _unwrap_event_envelope(payload)

    record_id = body.get("recordid", "") or ""
    trigger_time = body.get("datetime", "") or ""
    user = body.get("user", "") or ""
    error_message = body.get("errormessage", "") or ""

    # Auto-fill the trigger time when the caller did not supply one. This
    # eliminates the need for upstream systems to manually construct day-based
    # payloads. Datadog is consulted first (so the resolved time aligns with
    # the actual event), and we fall back to the current UTC time if the
    # search returns nothing or fails.
    if not trigger_time:
        from shared.datadog_resolver import resolve_trigger_time
        trigger_time = await resolve_trigger_time(user=user, record_id=record_id)
        log.info(f"invoke- auto-resolved trigger_time={trigger_time}")
        body = {**body, "datetime": trigger_time}

    input_info = {
        'record_id': record_id,
        'trigger_time': trigger_time,
        'user': user,
        'error_message': error_message,
    }
    raw_report_json = json.dumps(body, indent=2)

    prompt = (
        "System prompt (verbatim):\n"
        f"{_load_system_prompt()}\n\n"
        "Analyze the following One-Click Report entry and provide a full "
        "root cause analysis.\n\n"
        "After you finish the analysis, you must call the "
        "persist_analysis_artifacts tool exactly once before your final "
        "response. Pass your final analysis as the analysis_results argument "
        "and pass the original payload JSON as raw_report_data. If you "
        "identified Mulesoft correlation data, pass ctx_id and/or "
        "mulesoft_logs as well.\n\n"
        f"Please use the input data:\n{json.dumps(input_info, indent=2)}\n\n"
        f"Original payload JSON:\n{raw_report_json}"
    )

    agent = get_or_create_agent()
    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
