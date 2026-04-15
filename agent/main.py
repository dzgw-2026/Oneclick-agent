"""One-Click Report Analysis Agent — Strands on AgentCore Runtime.

Defines the agent with @tool-decorated functions for report parsing,
log lookups, and issue classification. Deployed on AgentCore Runtime.
"""

from __future__ import annotations

import json
import os
import sys

# Ensure the directory containing main.py (and all bundled packages) is on sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from tools.parse_report import parse_report as _parse_report, VLOCITY_ID_PATTERN, EXCEPTION_ID_PATTERN
from tools.classify_issue import classify_issue as _classify_issue
from tools.query_vlocity_logs import (
    get_vlocity_log_by_id as _get_vlocity_log,
    search_vlocity_logs as _search_vlocity,
)
from tools.query_exception_logs import (
    get_exception_log_by_id as _get_exception_log,
    search_exception_logs as _search_exceptions,
)


app = BedrockAgentCoreApp()
log = app.logger


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
    return _search_vlocity(user, start_time, end_time)


@tool
def get_exception_log_by_id(log_id: str) -> dict:
    """Look up a PS Exception Log by its Salesforce record ID. Returns
    exception type, severity, location, and error message.

    Args:
        log_id: Salesforce PS Exception Log ID (starts with 'a1W').
    """
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
    return _classify_issue(description, error_data)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH) as f:
        return f.read()


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
# AgentCore Runtime entrypoint
# ---------------------------------------------------------------------------

@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint. Receives report data and streams analysis."""
    log.info("Invoking One-Click Analysis Agent...")
    agent = get_or_create_agent()

    prompt = payload.get("prompt", "")
    if not prompt:
        # If raw report data is passed, wrap it in an analysis prompt
        report_data = {k: v for k, v in payload.items() if k != "prompt"}
        prompt = (
            "Analyze the following One-Click Report entry and provide a full "
            "root cause analysis.\n\n"
            f"Report Data:\n{json.dumps(report_data, indent=2)}"
        )

    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
