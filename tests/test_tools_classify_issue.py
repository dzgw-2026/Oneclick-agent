"""Unit tests for the classify_issue tool."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas"))

from tools.classify_issue import classify_issue


class TestClassifyIssue:
    def test_latency_spinning(self):
        result = classify_issue("SEARCHING USING SSN TO ADD PERSON IS JUST SPINNING")
        assert result["category"] == "LATENCY"
        assert result["confidence"] > 0

    def test_latency_frozen(self):
        result = classify_issue("SCREEN FROZE WHEN SEARCHING FOR APT FOR START")
        assert result["category"] == "LATENCY"
        assert "froze" in result["matched_keywords"]

    def test_latency_continuous(self):
        result = classify_issue("CONTINOUS LATENCY")
        assert result["category"] == "LATENCY"

    def test_ui_error_greyed_out(self):
        result = classify_issue("HEAT SOURCE ARE GREYED OUT")
        assert result["category"] == "UI_ERROR"

    def test_ui_error_wont_update(self):
        result = classify_issue("WHEN CLICKING UPDATE REQUIRED CONTACT VERIFICATION CCSP DOES NOT BRING UP PAGE TO UPDATE")
        assert result["category"] == "UI_ERROR"

    def test_auth_error(self):
        result = classify_issue("HAD TO AUTHENTICATE CALLER CARD MULTIPLE TIMES")
        assert result["category"] == "AUTH_ERROR"

    def test_auth_error_from_error_data(self):
        result = classify_issue("some issue", error_data="token not found, expired or invalid")
        assert result["category"] == "AUTH_ERROR"

    def test_data_error_from_error_data(self):
        result = classify_issue(
            "screen stuck",
            error_data="Conversion of value for field ScheduleDateTimeStart failed: Value is not valid for 'from' format."
        )
        assert result["category"] == "DATA_ERROR"

    def test_unknown_vague_description(self):
        result = classify_issue("something happened")
        assert result["category"] == "UNKNOWN"
        assert result["recording_review_needed"] is True

    def test_recording_review_needed_for_unknown(self):
        result = classify_issue("blah blah blah")
        assert result["recording_review_needed"] is True

    def test_recording_review_not_needed_with_clear_error(self):
        result = classify_issue(
            "SCREEN FROZE",
            error_data="code: 500, exception at CCSP_IP_GetRatesFlyoutInfo"
        )
        assert result["recording_review_needed"] is False
