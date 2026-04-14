"""Unit tests for query_exception_logs Lambda.

Tests that require DynamoDB are skipped when no local endpoint is available.
The handler response format is validated via the Bedrock event structure.
"""

import json
import sys
import os
import importlib.util
import unittest.mock as mock

import pytest

_mod_path = os.path.join(os.path.dirname(__file__), "..", "lambdas", "query_exception_logs", "handler.py")
_spec = importlib.util.spec_from_file_location("query_exception_handler", _mod_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

handler = _module.handler


class TestHandler:
    def test_handler_returns_bedrock_format_for_query_by_id(self):
        with mock.patch.object(_module, "get_exception_log_by_id", return_value={
            "Id": "a1WPf0000041jC6MAI",
            "ExceptionLogSeq": "E-090041389",
            "Application": "CCSP",
            "ExceptionLocation": "CCSP_IP_GetRatesFlyoutInfo",
            "ExceptionType": "System.TypeException",
            "SeverityLevel": "High",
            "ErrorMessage": "CCSP_IP_GetRatesFlyoutInfo Failed to fetch the response.",
        }):
            event = {
                "actionGroup": "QueryExceptionLogs",
                "apiPath": "/query-by-id",
                "parameters": [
                    {"name": "log_id", "value": "a1WPf0000041jC6MAI"}
                ],
                "requestBody": {},
            }
            result = handler(event, None)
            assert result["messageVersion"] == "1.0"
            assert result["response"]["httpStatusCode"] == 200
            body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
            assert "exceptions" in body
            assert body["count"] == 1
            assert body["exceptions"][0]["SeverityLevel"] == "High"

    def test_handler_returns_bedrock_format_for_search(self):
        with mock.patch.object(_module, "search_exception_logs", return_value=[]):
            event = {
                "actionGroup": "QueryExceptionLogs",
                "apiPath": "/search",
                "parameters": [
                    {"name": "application", "value": "CCSP"},
                    {"name": "location", "value": "CCSP_IP_GetRatesFlyoutInfo"},
                ],
                "requestBody": {},
            }
            result = handler(event, None)
            assert result["messageVersion"] == "1.0"
            assert result["response"]["httpStatusCode"] == 200
            body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
            assert body["count"] == 0
