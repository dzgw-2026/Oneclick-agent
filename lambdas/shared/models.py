"""Shared Pydantic data models for the One-Click Report Analysis Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OneClickReport(BaseModel):
    """A single row from a One-Click Report export."""

    user: str = Field(..., description="Agent LAN ID")
    datetime_str: str = Field(..., alias="datetime", description="Timestamp of the report")
    processidentifier: str = Field(default="", description="OmniScript process identifier")
    errormessage: str = Field(default="", description="Raw error message text")
    description: str = Field(default="", description="Agent-entered description of the issue")


class ParsedReport(BaseModel):
    """Result of parsing a One-Click Report row."""

    user: str
    datetime_str: str
    processidentifier: str
    errormessage: str
    description: str
    vlocity_log_ids: list[str] = Field(default_factory=list, description="Extracted Vlocity Error Log IDs")
    exception_log_ids: list[str] = Field(default_factory=list, description="Extracted PS Exception Log IDs")
    omniscript_name: str = Field(default="", description="Mapped OmniScript name from processidentifier")


class VlocityErrorLog(BaseModel):
    """A Vlocity Error Log record from Salesforce."""

    Id: str
    Name: str
    ErrorCode: str = ""
    Functionality: str = ""
    Status: str = ""
    ContextId: str = ""
    SourceName: str = ""
    NumberOfRetry: int = 0
    HTTPRequest: str = ""
    HTTPResponse: str = ""
    User: str = ""
    Datetime: str = ""
    ProcessIdentifier: str = ""
    ExceptionLogId: Optional[str] = None


class ParsedVlocityLog(BaseModel):
    """Vlocity Error Log with parsed HTTP request/response."""

    Id: str
    Name: str
    ErrorCode: str
    Functionality: str
    Status: str
    ContextId: str
    SourceName: str
    User: str
    Datetime: str
    ProcessIdentifier: str
    request_data: dict = Field(default_factory=dict)
    response_data: dict = Field(default_factory=dict)
    response_code: str = ""
    response_status: str = ""
    response_integration: str = ""
    error_details: str = ""
    exception_log_id: Optional[str] = None


class PSExceptionLog(BaseModel):
    """A PS Exception Log record from Salesforce."""

    Id: str
    ExceptionLogSeq: str = ""
    Application: str = ""
    ExceptionLocation: str = ""
    ExceptionType: str = ""
    SeverityLevel: str = ""
    ErrorMessage: str = ""
    LineNumber: int = 0
    Owner: str = ""
    CreatedBy: str = ""
    CreatedDate: str = ""
    LastModifiedBy: str = ""
    LastModifiedDate: str = ""


class IssueClassification(BaseModel):
    """Result of classifying an issue from agent description."""

    category: str = Field(..., description="LATENCY | UI_ERROR | AUTH_ERROR | DATA_ERROR | UNKNOWN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence 0-1")
    recording_review_needed: bool = Field(default=True, description="Whether user recording review is required")
    matched_keywords: list[str] = Field(default_factory=list, description="Keywords that triggered classification")


class AnalysisResult(BaseModel):
    """Final analysis output for a One-Click Report."""

    report_user: str
    report_datetime: str
    omniscript: str = ""
    issue_category: str = ""
    issue_confidence: float = 0.0
    recording_review_needed: bool = True
    root_cause: str = ""
    severity: str = ""
    vlocity_logs_found: list[ParsedVlocityLog] = Field(default_factory=list)
    exception_logs_found: list[PSExceptionLog] = Field(default_factory=list)
    recommended_action: str = ""
    human_summary: str = ""
