"""Unit tests for the intake Lambda handler."""

import json
import sys
import os
import unittest.mock as mock

# Allow imports from lambdas/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas"))

from handler import handler, invoke_agentcore


class TestIntakeValidation:
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


class TestInvokeAgentCore:
    def test_forwards_to_agentcore_and_returns_analysis(self):
        """Intake Lambda invokes AgentCore Runtime and returns streamed result."""
        mock_response = {
            "body": [
                {"chunk": {"bytes": b"Analysis "}},
                {"chunk": {"bytes": b"complete."}},
            ]
        }
        with mock.patch("handler.boto3") as mock_boto3:
            mock_client = mock.MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.invoke_agent_runtime.return_value = mock_response

            result = invoke_agentcore({"user": "G2CD", "description": "SCREEN FROZE"})
            assert result["analysis"] == "Analysis complete."
            mock_client.invoke_agent_runtime.assert_called_once()

    def test_handler_success_includes_session_id(self):
        """Full handler flow returns 200 with session_id."""
        mock_response = {
            "body": [
                {"chunk": {"bytes": b"Root cause found."}},
            ]
        }
        with mock.patch("handler.boto3") as mock_boto3:
            mock_client = mock.MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.invoke_agent_runtime.return_value = mock_response

            event = {"body": json.dumps({"user": "G2CD", "description": "SCREEN FROZE"})}
            result = handler(event, None)
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert "analysis" in body
            assert "session_id" in body
            assert body["analysis"] == "Root cause found."

    def test_handler_returns_500_on_agentcore_error(self):
        """Handler returns 500 if AgentCore invocation fails."""
        with mock.patch("handler.boto3") as mock_boto3:
            mock_client = mock.MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.invoke_agent_runtime.side_effect = Exception("Runtime unavailable")

            event = {"body": json.dumps({"user": "G2CD", "description": "test"})}
            result = handler(event, None)
            assert result["statusCode"] == 500
            body = json.loads(result["body"])
            assert "Agent invocation failed" in body["error"]
