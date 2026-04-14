"""Unit tests for parse_report Lambda."""

import json
import sys
import os
import importlib.util

_mod_path = os.path.join(os.path.dirname(__file__), "..", "lambdas", "parse_report", "handler.py")
_spec = importlib.util.spec_from_file_location("parse_report_handler", _mod_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

extract_salesforce_ids = _module.extract_salesforce_ids
parse_report = _module.parse_report
handler = _module.handler


class TestExtractSalesforceIds:
    def test_extracts_vlocity_log_id(self):
        msg = "URL: https://pgeservice.my.salesforce.com/a9zPf00006qJl8IAE ContextId: 2026-03-27"
        ids = extract_salesforce_ids(msg)
        assert "a9zPf00006qJl8IAE" in ids["vlocity_log_ids"]
        assert len(ids["exception_log_ids"]) == 0

    def test_extracts_exception_log_id(self):
        msg = "Exception Logs: Id: a1WPf0000041jC6MAI Exception Location: CCSP_IP_GetRatesFlyoutInfo"
        ids = extract_salesforce_ids(msg)
        assert "a1WPf0000041jC6MAI" in ids["exception_log_ids"]
        assert len(ids["vlocity_log_ids"]) == 0

    def test_extracts_both_id_types(self):
        msg = "a9zPf000005MQAf and also a1WPf0000041jC6MAI"
        ids = extract_salesforce_ids(msg)
        assert len(ids["vlocity_log_ids"]) == 1
        assert len(ids["exception_log_ids"]) == 1

    def test_no_ids_in_empty_message(self):
        ids = extract_salesforce_ids("")
        assert ids["vlocity_log_ids"] == []
        assert ids["exception_log_ids"] == []

    def test_no_ids_in_plain_text(self):
        ids = extract_salesforce_ids("SCREEN FROZE WHEN SEARCHING FOR APT")
        assert ids["vlocity_log_ids"] == []
        assert ids["exception_log_ids"] == []

    def test_deduplicates_ids(self):
        msg = "a9zPf00006qJl8IAE and again a9zPf00006qJl8IAE"
        ids = extract_salesforce_ids(msg)
        assert len(ids["vlocity_log_ids"]) == 1


class TestParseReport:
    def test_parses_full_report(self):
        report = {
            "user": "G2CD",
            "datetime": "2026-03-27T16:44:00.000Z",
            "processidentifier": "cCSPMultiStartServiceEnglish",
            "errormessage": "URL: https://pgeservice.my.salesforce.com/a9zPf00006qJl8IAE",
            "description": "SCREEN FROZE WHEN SEARCHING FOR APT FOR START",
        }
        result = parse_report(report)
        assert result["user"] == "G2CD"
        assert result["omniscript_name"] == "cCSPMultiStartServiceEnglish"
        assert result["has_direct_ids"] is True
        assert "a9zPf00006qJl8IAE" in result["vlocity_log_ids"]

    def test_parses_report_without_ids(self):
        report = {
            "user": "J25E",
            "datetime": "2026-03-27T16:42:00.000Z",
            "processidentifier": "",
            "errormessage": "",
            "description": "CONTINOUS LATENCY",
        }
        result = parse_report(report)
        assert result["omniscript_name"] == "UNKNOWN"
        assert result["has_direct_ids"] is False

    def test_parses_report_with_exception_id(self):
        report = {
            "user": "ZXV4",
            "datetime": "2026-03-27T15:29:00.000Z",
            "processidentifier": "cCSPMultiStartServiceEnglish",
            "errormessage": "Exception Logs: Id: a1WPf0000041jC6MAI Exception Location: CCSP_IP_GetRatesFlyoutInfo",
            "description": "CCSP DOES NOT BRING UP RES RATES",
        }
        result = parse_report(report)
        assert "a1WPf0000041jC6MAI" in result["exception_log_ids"]
        assert result["has_direct_ids"] is True


class TestHandler:
    def test_handler_returns_bedrock_format(self):
        event = {
            "actionGroup": "ParseReport",
            "apiPath": "/parse",
            "parameters": [],
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "user", "value": "G2CD"},
                            {"name": "datetime", "value": "2026-03-27T16:44:00.000Z"},
                            {"name": "processidentifier", "value": "cCSPMultiStartServiceEnglish"},
                            {"name": "errormessage", "value": ""},
                            {"name": "description", "value": "SCREEN FROZE"},
                        ]
                    }
                }
            },
        }
        result = handler(event, None)
        assert result["messageVersion"] == "1.0"
        assert result["response"]["httpStatusCode"] == 200
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert body["user"] == "G2CD"
