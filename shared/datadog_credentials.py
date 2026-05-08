"""Datadog credentials management — shared across the agent and helpers.

Provides cached access to Datadog API/application keys stored in AWS
Secrets Manager. Extracted from main.py so other shared modules (e.g.
the datetime resolver) can reuse the same cached credentials without
introducing a circular import.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError


log = logging.getLogger(__name__)

_datadog_credentials: dict | None = None


def get_datadog_credentials() -> dict:
    """Fetch Datadog credentials from AWS Secrets Manager.

    Returns:
        dict: Contains 'api_key', 'application_key', and 'endpoint'.
    """
    global _datadog_credentials

    if _datadog_credentials is not None:
        return _datadog_credentials

    secret_name = os.environ.get('DATADOG_SECRET_NAME', 'temp_datadog_credentials')
    region_name = os.environ.get('AWS_REGION', 'us-east-1')

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name,
    )

    try:
        log.info(f"Fetching Datadog credentials from Secrets Manager: {secret_name}")
        response = client.get_secret_value(SecretId=secret_name)

        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            _datadog_credentials = {
                'api_key': secret.get('DD_API_KEY', ''),
                'application_key': secret.get('DD_APPLICATION_KEY', ''),
                'endpoint': secret.get(
                    'DD_ENDPOINT',
                    'https://api.datadoghq.com/api/v2/logs/events/search',
                ),
            }
            log.info("Successfully fetched Datadog credentials")
            return _datadog_credentials

        log.error("Secret does not contain SecretString")
        raise ValueError("Secret format is invalid")

    except ClientError as e:
        log.error(f"Error fetching secret: {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error fetching Datadog credentials: {e}")
        raise
