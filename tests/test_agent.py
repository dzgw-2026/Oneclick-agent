"""Unit tests for the agent entrypoint handler."""

import json
import sys
import os
import unittest.mock as mock

# Allow imports from lambdas/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas"))

from handler import handler, run_agent, _execute_tool


class TestEntrypointValidation:
    def test_rejects_missing_user(self):
        event = {"body": json.dumps({"description": "test"})}
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "user" in body["error"]

    def test_rejects_missing_description(self):
        event = {"body": json.dumps({"user": "G2CD"})}
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "description" in body["error"]

    def test_rejects_invalid_json(self):
        event = {"body": "not json"}
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "Invalid JSON" in body["error"]

    def test_rejects_empty_body(self):
        event = {"body": "{}"}
        result = handler(event, None)
        assert result["statusCode"] == 400


class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        result = _execute_tool("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_parse_report_tool_dispatch(self):
        result = _execute_tool("parse_report", {
            "user": "G2CD",
            "datetime": "2026-03-27T16:44:00.000Z",
            "processidentifier": "cCSPMultiStartServiceEnglish",
            "errormessage": "URL: https://pgeservice.my.salesforce.com/a9zPf00006qJl8IAE",
            "description": "SCREEN FROZE",
        })
        assert result["user"] == "G2CD"
        assert result["has_direct_ids"] is True

    def test_classify_issue_tool_dispatch(self):
        result = _execute_tool("classify_issue", {
            "description": "SCREEN FROZE WHEN SEARCHING",
        })
        assert result["category"] == "LATENCY"


class TestRunAgent:
    def test_single_turn_end(self):
        """Agent returns a final text response on the first turn."""
        mock_response = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Analysis complete."}],
                }
            },
        }
        with mock.patch("handler.boto3") as mock_boto3:
            mock_client = mock.MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.converse.return_value = mock_response

            result = run_agent({"user": "G2CD", "description": "test"})
            assert result["analysis"] == "Analysis complete."

    def test_tool_use_then_end(self):
        """Agent calls a tool, gets the result, and then ends."""
        tool_use_response = {
            "stopReason": "tool_use",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-123",
                                "name": "parse_report",
                                "input": {
                                    "user": "G2CD",
                                    "description": "SCREEN FROZE",
                                },
                            }
                        }
                    ],
                }
            },
        }
        end_response = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Root cause identified."}],
                }
            },
        }
        with mock.patch("handler.boto3") as mock_boto3:
            mock_client = mock.MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.converse.side_effect = [tool_use_response, end_response]

            result = run_agent({"user": "G2CD", "description": "SCREEN FROZE"})
            assert result["analysis"] == "Root cause identified."
            assert mock_client.converse.call_count == 2
