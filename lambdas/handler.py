"""One-Click Report Analysis Agent — Bedrock Converse API with tool use.

Receives One-Click Report data via POST /analyze, runs a tool-use loop
with Claude via the Bedrock Converse API, and returns the analysis result.
Replaces the previous Bedrock Agent + Lambda action-group architecture with
a single Lambda that executes tools in-process.
"""

from __future__ import annotations

import json
import os
import uuid

import boto3

from tools.definitions import TOOL_CONFIG
from tools.parse_report import parse_report
from tools.query_vlocity_logs import get_vlocity_log_by_id, search_vlocity_logs
from tools.query_exception_logs import get_exception_log_by_id, search_exception_logs
from tools.classify_issue import classify_issue


MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
REGION = os.environ.get("AWS_REGION_OVERRIDE", os.environ.get("AWS_REGION", "us-west-2"))
MAX_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "15"))

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")


def _load_system_prompt() -> str:
    """Load the agent system prompt from the bundled text file."""
    with open(_SYSTEM_PROMPT_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "parse_report": lambda params: parse_report(params),
    "get_vlocity_log_by_id": lambda params: get_vlocity_log_by_id(params["log_id"]),
    "search_vlocity_logs": lambda params: search_vlocity_logs(
        params["user"], params["start_time"], params["end_time"]
    ),
    "get_exception_log_by_id": lambda params: get_exception_log_by_id(params["log_id"]),
    "search_exception_logs": lambda params: search_exception_logs(
        params.get("application", ""), params.get("location", "")
    ),
    "classify_issue": lambda params: classify_issue(
        params["description"], params.get("error_data", "")
    ),
}


def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool by name and return the result as a JSON-serialisable dict."""
    fn = TOOL_DISPATCH.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(tool_input)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(report_data: dict) -> dict:
    """Run the Converse API tool-use loop and return the final analysis."""
    client = boto3.client("bedrock-runtime", region_name=REGION)
    system_prompt = _load_system_prompt()

    user_message = (
        "Analyze the following One-Click Report entry and provide a full "
        "root cause analysis.\n\n"
        f"Report Data:\n{json.dumps(report_data, indent=2)}"
    )

    messages = [{"role": "user", "content": [{"text": user_message}]}]

    for _ in range(MAX_TURNS):
        response = client.converse(
            modelId=MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

        stop_reason = response["stopReason"]
        assistant_message = response["output"]["message"]
        messages.append(assistant_message)

        if stop_reason == "end_turn":
            # Extract final text from the assistant's last message
            for block in assistant_message["content"]:
                if "text" in block:
                    return {"analysis": block["text"]}
            return {"analysis": ""}

        if stop_reason == "tool_use":
            # Execute every tool the model requested, collect results
            tool_results = []
            for block in assistant_message["content"]:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    result = _execute_tool(tool_use["name"], tool_use["input"])
                    tool_results.append(
                        {
                            "toolResult": {
                                "toolUseId": tool_use["toolUseId"],
                                "content": [{"json": result}],
                            }
                        }
                    )

            # Feed tool results back as a user message for the next turn
            messages.append({"role": "user", "content": tool_results})
        else:
            return {"analysis": f"Agent stopped unexpectedly: {stop_reason}"}

    return {"analysis": "Agent reached maximum turns without completing analysis."}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def handler(event, context):
    """Lambda handler for API Gateway integration."""
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            report_data = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON in request body"}),
            }
    else:
        report_data = body

    if not report_data.get("user"):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing required field: user"}),
        }

    if not report_data.get("description"):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing required field: description"}),
        }

    try:
        session_id = str(uuid.uuid4())
        result = run_agent(report_data)
        result["session_id"] = session_id

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Agent invocation failed: {str(e)}"}),
        }
