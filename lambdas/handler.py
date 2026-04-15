"""One-Click Report Analysis Agent — Intake Lambda.

Receives One-Click Report data via POST /analyze, validates the request,
and forwards it to the Strands agent running on AgentCore Runtime.
"""

from __future__ import annotations

import json
import os
import uuid

import boto3


AGENT_RUNTIME_ID = os.environ.get("AGENT_RUNTIME_ID", "")
AGENT_NAME = os.environ.get("AGENT_NAME", "OneClickAgent")
REGION = os.environ.get("AWS_REGION_OVERRIDE", os.environ.get("AWS_REGION", "us-west-2"))


def invoke_agentcore(report_data: dict) -> dict:
    """Invoke the Strands agent on AgentCore Runtime with the report data."""
    client = boto3.client("bedrock-agentcore", region_name=REGION)

    prompt = (
        "Analyze the following One-Click Report entry and provide a full "
        "root cause analysis.\n\n"
        f"Report Data:\n{json.dumps(report_data, indent=2)}"
    )

    payload = {"prompt": prompt}
    payload.update(report_data)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ID,
        payload=json.dumps(payload),
    )

    # Collect the streamed response
    result_text = ""
    if "body" in response:
        for chunk in response["body"]:
            if "chunk" in chunk:
                result_text += chunk["chunk"].get("bytes", b"").decode("utf-8")
            elif isinstance(chunk, (str, bytes)):
                result_text += chunk if isinstance(chunk, str) else chunk.decode("utf-8")

    if not result_text:
        result_text = json.dumps(response.get("output", {}))

    return {"analysis": result_text}


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
        result = invoke_agentcore(report_data)
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
