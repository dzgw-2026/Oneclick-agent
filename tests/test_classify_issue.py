"""Unit tests for classify_issue Lambda."""

import json
import sys
import os
import importlib.util

_mod_path = os.path.join(os.path.dirname(__file__), "..", "lambdas", "classify_issue", "handler.py")
_spec = importlib.util.spec_from_file_location("classify_handler", _mod_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

classify_description = _module.classify_description
handler = _module.handler


class TestClassifyDescription:
    def test_latency_spinning(self):
        result = classify_description("SEARCHING USING SSN TO ADD PERSON IS JUST SPINNING")
        assert result["category"] == "LATENCY"
        assert result["confidence"] > 0

    def test_latency_frozen(self):
        result = classify_description("SCREEN FROZE WHEN SEARCHING FOR APT FOR START")
        assert result["category"] == "LATENCY"
        assert "froze" in result["matched_keywords"]

    def test_latency_continuous(self):
        result = classify_description("CONTINOUS LATENCY")
        assert result["category"] == "LATENCY"

    def test_ui_error_greyed_out(self):
        result = classify_description("HEAT SOURCE ARE GREYED OUT")
        assert result["category"] == "UI_ERROR"

    def test_ui_error_wont_update(self):
        result = classify_description("WHEN CLICKING UPDATE REQUIRED CONTACT VERIFICATION CCSP DOES NOT BRING UP PAGE TO UPDATE")
        assert result["category"] == "UI_ERROR"

    def test_auth_error(self):
        result = classify_description("HAD TO AUTHENTICATE CALLER CARD MULTIPLE TIMES")
        assert result["category"] == "AUTH_ERROR"

    def test_auth_error_from_error_data(self):
        result = classify_description("some issue", error_data="token not found, expired or invalid")
        assert result["category"] == "AUTH_ERROR"

    def test_data_error_from_error_data(self):
        result = classify_description(
            "screen stuck",
            error_data="Conversion of value for field ScheduleDateTimeStart failed: Value is not valid for 'from' format."
        )
        assert result["category"] == "DATA_ERROR"

    def test_unknown_vague_description(self):
        result = classify_description("something happened")
        assert result["category"] == "UNKNOWN"
        assert result["recording_review_needed"] is True

    def test_recording_review_needed_for_unknown(self):
        result = classify_description("blah blah blah")
        assert result["recording_review_needed"] is True

    def test_recording_review_not_needed_with_clear_error(self):
        result = classify_description(
            "SCREEN FROZE",
            error_data="code: 500, exception at CCSP_IP_GetRatesFlyoutInfo"
        )
        assert result["recording_review_needed"] is False


class TestHandler:
    def test_handler_returns_bedrock_format(self):
        event = {
            "actionGroup": "ClassifyIssue",
            "apiPath": "/classify",
            "parameters": [],
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "description", "value": "SCREEN FROZE WHEN SEARCHING"},
                            {"name": "error_data", "value": ""},
                        ]
                    }
                }
            },
        }
        result = handler(event, None)
        assert result["messageVersion"] == "1.0"
        assert result["response"]["httpStatusCode"] == 200
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert body["category"] == "LATENCY"
