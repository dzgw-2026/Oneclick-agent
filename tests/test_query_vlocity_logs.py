"""Unit tests for query_vlocity_logs Lambda."""

import json
import sys
import os
import importlib.util

_mod_path = os.path.join(os.path.dirname(__file__), "..", "lambdas", "query_vlocity_logs", "handler.py")
_spec = importlib.util.spec_from_file_location("query_vlocity_handler", _mod_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

parse_http_payload = _module.parse_http_payload
enrich_log = _module.enrich_log


class TestParseHttpPayload:
    def test_parses_valid_json(self):
        raw = '{"code": "500", "status": "failure"}'
        result = parse_http_payload(raw)
        assert result["code"] == "500"
        assert result["status"] == "failure"

    def test_returns_empty_for_empty_string(self):
        assert parse_http_payload("") == {}

    def test_returns_raw_for_invalid_json(self):
        result = parse_http_payload("not json at all")
        assert result == {"raw": "not json at all"}

    def test_returns_empty_for_none(self):
        assert parse_http_payload(None) == {}


class TestEnrichLog:
    def test_enriches_log_with_field_order_error(self):
        log = {
            "Id": "a9zPf00006plusIAU",
            "Name": "a9zPf00006plusIAU",
            "ErrorCode": "500",
            "Functionality": "UpdateFAFO",
            "Status": "Failure",
            "ContextId": "2026-03-27T10:00:17:d628c5fe",
            "SourceName": "Integration Handler Apex Class",
            "User": "JH37",
            "Datetime": "2026-03-27T16:07:00.000Z",
            "ProcessIdentifier": "cCSPMultiStartServiceEnglish",
            "HTTPRequest": "{}",
            "HTTPResponse": json.dumps({
                "code": "500",
                "status": "failure",
                "integration": "update-fieldorder",
                "details": {
                    "fieldorders": [{
                        "fieldorderid": "1045530874",
                        "response": {
                            "code": "500",
                            "status": "failure",
                            "message": "Conversion of value for field ScheduleDateTimeStart failed"
                        }
                    }]
                }
            })
        }
        result = enrich_log(log)
        assert result["response_code"] == "500"
        assert result["response_integration"] == "update-fieldorder"
        assert "ScheduleDateTimeStart" in result["error_details"]

    def test_enriches_log_with_token_error(self):
        log = {
            "Id": "a9zPf000005MQAf",
            "Name": "a9zPf000005MQAf",
            "ErrorCode": "200",
            "Functionality": "saveDetailsToOnTrack",
            "Status": "Success",
            "ContextId": "ctx",
            "SourceName": "Integration Handler Apex Class",
            "User": "NAJ8",
            "Datetime": "2026-03-11T22:48:34.368Z",
            "ProcessIdentifier": "cCSPCreateServiceRequestEnglish",
            "HTTPRequest": "{}",
            "HTTPResponse": json.dumps({
                "code": "200",
                "status": "success",
                "integration": "SubmitFeedback",
                "details": {"message": "Feedback submitted successfully"}
            })
        }
        result = enrich_log(log)
        assert result["response_code"] == "200"
        assert result["response_status"] == "success"

    def test_enriches_log_with_exception_id(self):
        log = {
            "Id": "test",
            "Name": "test",
            "ErrorCode": "500",
            "Functionality": "GetRatesFlyoutInfo",
            "Status": "Failure",
            "ContextId": "",
            "SourceName": "",
            "User": "ZXV4",
            "Datetime": "2026-03-27T15:29:00.000Z",
            "ProcessIdentifier": "cCSPMultiStartServiceEnglish",
            "ExceptionLogId": "a1WPf0000041jC6MAI",
            "HTTPRequest": "{}",
            "HTTPResponse": json.dumps({
                "code": "500",
                "status": "failure",
                "details": {"message": "CCSP_IP_GetRatesFlyoutInfo Failed to fetch the response."}
            })
        }
        result = enrich_log(log)
        assert result["exception_log_id"] == "a1WPf0000041jC6MAI"
        assert "Failed to fetch" in result["error_details"]
