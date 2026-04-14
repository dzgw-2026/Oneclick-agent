"""Tool definitions for the Bedrock Converse API.

Each tool maps to a function that the agent can invoke during analysis.
These replace the previous Bedrock Agent action groups / Lambda-backed tools.
"""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "parse_report",
                "description": (
                    "Parse a One-Click Report to extract structured data and identify "
                    "embedded Salesforce record IDs (Vlocity Error Log IDs starting with "
                    "'a9z' and PS Exception Log IDs starting with 'a1W')."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "string",
                                "description": "Agent LAN ID",
                            },
                            "datetime": {
                                "type": "string",
                                "description": "Report timestamp (ISO 8601)",
                            },
                            "processidentifier": {
                                "type": "string",
                                "description": "OmniScript process identifier",
                            },
                            "errormessage": {
                                "type": "string",
                                "description": "Raw error message text",
                            },
                            "description": {
                                "type": "string",
                                "description": "Agent-entered description of the issue",
                            },
                        },
                        "required": ["user"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_vlocity_log_by_id",
                "description": (
                    "Look up a Vlocity Error Log by its Salesforce record ID. "
                    "Returns the full log including HTTP request/response payloads "
                    "with parsed error details."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "log_id": {
                                "type": "string",
                                "description": "Salesforce Vlocity Error Log ID (starts with 'a9z')",
                            },
                        },
                        "required": ["log_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "search_vlocity_logs",
                "description": (
                    "Search for Vlocity Error Logs by agent LAN ID and time range. "
                    "Use when no direct log IDs are available in the report. "
                    "Search ±30 minutes around the report timestamp."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "string",
                                "description": "Agent LAN ID",
                            },
                            "start_time": {
                                "type": "string",
                                "description": "Start of time window (ISO 8601)",
                            },
                            "end_time": {
                                "type": "string",
                                "description": "End of time window (ISO 8601)",
                            },
                        },
                        "required": ["user", "start_time", "end_time"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_exception_log_by_id",
                "description": (
                    "Look up a PS Exception Log by its Salesforce record ID. "
                    "Returns exception type, severity, location, and error message."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "log_id": {
                                "type": "string",
                                "description": "Salesforce PS Exception Log ID (starts with 'a1W')",
                            },
                        },
                        "required": ["log_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "search_exception_logs",
                "description": (
                    "Search PS Exception Logs by application name and/or exception "
                    "location (class name). Use to find related exceptions when you "
                    "know the application or error location."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "application": {
                                "type": "string",
                                "description": "Application name (e.g., 'CCSP')",
                            },
                            "location": {
                                "type": "string",
                                "description": "Exception location / class name (e.g., 'CCSP_IP_GetRatesFlyoutInfo')",
                            },
                        },
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "classify_issue",
                "description": (
                    "Classify an issue based on the agent's description text and any "
                    "error data gathered from log lookups. Returns category (LATENCY, "
                    "UI_ERROR, AUTH_ERROR, DATA_ERROR, UNKNOWN), confidence score, "
                    "and whether recording review is needed."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Agent-entered description of the issue",
                            },
                            "error_data": {
                                "type": "string",
                                "description": "Error data gathered from log lookups (optional)",
                            },
                        },
                        "required": ["description"],
                    }
                },
            }
        },
    ]
}
