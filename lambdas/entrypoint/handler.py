"""Entrypoint Lambda — API Gateway → Bedrock Agent.

Receives One-Click Report data via POST /analyze, invokes the Bedrock Agent
session, collects the response, and returns the analysis result.
"""

from __future__ import annotations

import json
import os
import uuid

import boto3


AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")


def invoke_agent(report_data: dict) -> dict:
    """Invoke the Bedrock Agent with One-Click Report data and collect the response."""
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    session_id = str(uuid.uuid4())

    # Format the input prompt for the agent
    prompt = (
        "Analyze the following One-Click Report entry and provide a full root cause analysis.\n\n"
        f"Report Data:\n{json.dumps(report_data, indent=2)}"
    )

    response = client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=prompt,
    )

    # Collect streamed response chunks
    completion = ""
    for event in response.get("completion", []):
        if "chunk" in event:
            chunk_data = event["chunk"]
            if "bytes" in chunk_data:
                completion += chunk_data["bytes"].decode("utf-8")

    return {
        "session_id": session_id,
        "analysis": completion,
    }


def handler(event, context):
    """Lambda handler for API Gateway integration."""
    # Parse request body
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

    # Validate required fields
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
        result = invoke_agent(report_data)

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
