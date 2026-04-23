"""Salesforce client interface — mock implementation backed by DynamoDB.

Swap to real Salesforce by setting SF_MODE=live and providing credentials
in AWS Secrets Manager. The interface stays the same.
"""

from __future__ import annotations

import os
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr


VLOCITY_TABLE = os.environ.get("VLOCITY_TABLE", "VlocityErrorLogs")
EXCEPTION_TABLE = os.environ.get("EXCEPTION_TABLE", "PSExceptionLogs")


def _get_dynamodb_resource():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    if endpoint_url:
        return boto3.resource("dynamodb", endpoint_url=endpoint_url)
    return boto3.resource("dynamodb")


def get_vlocity_log_by_id(log_id: str) -> Optional[dict]:
    """Look up a Vlocity Error Log by its Salesforce ID."""
    table = _get_dynamodb_resource().Table(VLOCITY_TABLE)
    response = table.get_item(Key={"Id": log_id})
    return response.get("Item")


def search_vlocity_logs(user: str, start_time: str, end_time: str) -> list[dict]:
    """Search Vlocity Error Logs by agent LAN ID and time range."""
    table = _get_dynamodb_resource().Table(VLOCITY_TABLE)
    response = table.query(
        IndexName="User-Datetime-index",
        KeyConditionExpression=Key("User").eq(user) & Key("Datetime").between(start_time, end_time),
    )
    return response.get("Items", [])


def get_exception_log_by_id(log_id: str) -> Optional[dict]:
    """Look up a PS Exception Log by its Salesforce ID."""
    table = _get_dynamodb_resource().Table(EXCEPTION_TABLE)
    response = table.get_item(Key={"Id": log_id})
    return response.get("Item")


def search_exception_logs(application: str = "", location: str = "") -> list[dict]:
    """Search PS Exception Logs by application and/or location."""
    table = _get_dynamodb_resource().Table(EXCEPTION_TABLE)

    filter_expr = None
    if application:
        filter_expr = Attr("Application").eq(application)
    if location:
        loc_filter = Attr("ExceptionLocation").eq(location)
        filter_expr = filter_expr & loc_filter if filter_expr else loc_filter

    if filter_expr:
        response = table.scan(FilterExpression=filter_expr)
    else:
        response = table.scan()

    return response.get("Items", [])
