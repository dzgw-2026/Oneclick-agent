"""Unit tests for the query_exception_logs tool."""

import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas"))

from tools import query_exception_logs


class TestGetExceptionLogById:
    def test_returns_log_when_found(self):
        mock_log = {
            "Id": "a1WPf0000041jC6MAI",
            "ExceptionLogSeq": "E-090041389",
            "Application": "CCSP",
            "ExceptionLocation": "CCSP_IP_GetRatesFlyoutInfo",
            "ExceptionType": "System.TypeException",
            "SeverityLevel": "High",
            "ErrorMessage": "CCSP_IP_GetRatesFlyoutInfo Failed to fetch the response.",
        }
        with mock.patch.object(query_exception_logs, "_get_by_id", return_value=mock_log):
            result = query_exception_logs.get_exception_log_by_id("a1WPf0000041jC6MAI")
            assert result["count"] == 1
            assert result["exceptions"][0]["SeverityLevel"] == "High"

    def test_returns_empty_when_not_found(self):
        with mock.patch.object(query_exception_logs, "_get_by_id", return_value=None):
            result = query_exception_logs.get_exception_log_by_id("nonexistent")
            assert result["count"] == 0
            assert result["exceptions"] == []


class TestSearchExceptionLogs:
    def test_returns_matching_logs(self):
        with mock.patch.object(query_exception_logs, "_search", return_value=[{"Id": "test"}]):
            result = query_exception_logs.search_exception_logs(
                application="CCSP", location="CCSP_IP_GetRatesFlyoutInfo"
            )
            assert result["count"] == 1

    def test_returns_empty_for_no_matches(self):
        with mock.patch.object(query_exception_logs, "_search", return_value=[]):
            result = query_exception_logs.search_exception_logs(application="CCSP")
            assert result["count"] == 0
