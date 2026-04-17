"""One-Click Report Analysis Agent — Strands on AgentCore Runtime.

Defines the agent with @tool-decorated functions for report parsing,
log lookups, and issue classification. Deployed on AgentCore Runtime.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
import boto3
from botocore.exceptions import ClientError

# Ensure the directory containing main.py (and all bundled packages) is on sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from tools.parse_report import parse_report as _parse_report, VLOCITY_ID_PATTERN, EXCEPTION_ID_PATTERN
from tools.classify_issue import classify_issue as _classify_issue
from tools.query_vlocity_logs import (
    get_vlocity_log_by_id as _get_vlocity_log,
    search_vlocity_logs as _search_vlocity,
)
from tools.query_exception_logs import (
    get_exception_log_by_id as _get_exception_log,
    search_exception_logs as _search_exceptions,
)


app = BedrockAgentCoreApp()
log = app.logger


# ---------------------------------------------------------------------------
# Datadog Credentials Management
# ---------------------------------------------------------------------------

_datadog_credentials = None


def get_datadog_credentials() -> dict:
    """Fetch Datadog credentials from AWS Secrets Manager.
    
    Returns:
        dict: Contains 'api_key', 'application_key', and 'endpoint'
    """
    global _datadog_credentials
    
    # Return cached credentials if available
    if _datadog_credentials is not None:
        return _datadog_credentials
    
    secret_name = os.environ.get('DATADOG_SECRET_NAME', 'temp_datadog_credentials')
    region_name = os.environ.get('AWS_REGION', 'us-east-1')
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        log.info(f"Fetching Datadog credentials from Secrets Manager: {secret_name}")
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            _datadog_credentials = {
                'api_key': secret.get('DD_API_KEY', ''),
                'application_key': secret.get('DD_APPLICATION_KEY', ''),
                'endpoint': secret.get('DD_ENDPOINT', 'https://api.datadoghq.com/api/v2/logs/events/search')
            }
            log.info("Successfully fetched Datadog credentials")
            return _datadog_credentials
        else:
            log.error("Secret does not contain SecretString")
            raise ValueError("Secret format is invalid")
            
    except ClientError as e:
        log.error(f"Error fetching secret: {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error fetching Datadog credentials: {e}")
        raise


# ---------------------------------------------------------------------------
# Tools — @tool wrappers around the module implementations
# ---------------------------------------------------------------------------

@tool
def parse_report(
    user: str,
    datetime: str = "",
    processidentifier: str = "",
    errormessage: str = "",
    description: str = "",
) -> dict:
    """Parse a One-Click Report to extract structured data and identify
    embedded Salesforce record IDs (Vlocity Error Log IDs starting with
    'a9z' and PS Exception Log IDs starting with 'a1W').

    Args:
        user: Agent LAN ID.
        datetime: Report timestamp (ISO 8601).
        processidentifier: OmniScript process identifier.
        errormessage: Raw error message text.
        description: Agent-entered description of the issue.
    """
    return _parse_report({
        "user": user,
        "datetime": datetime,
        "processidentifier": processidentifier,
        "errormessage": errormessage,
        "description": description,
    })


@tool
def get_vlocity_log_by_id(log_id: str) -> dict:
    """Look up a Vlocity Error Log by its Salesforce record ID. Returns the
    full log including HTTP request/response payloads with parsed error details.

    Args:
        log_id: Salesforce Vlocity Error Log ID (starts with 'a9z').
    """
    return _get_vlocity_log(log_id)


@tool
def search_vlocity_logs(user: str, start_time: str, end_time: str) -> dict:
    """Search for Vlocity Error Logs by agent LAN ID and time range. Use when
    no direct log IDs are available in the report. Search +/- 30 minutes around
    the report timestamp.

    Args:
        user: Agent LAN ID.
        start_time: Start of time window (ISO 8601).
        end_time: End of time window (ISO 8601).
    """
    return _search_vlocity(user, start_time, end_time)


@tool
def get_exception_log_by_id(log_id: str) -> dict:
    """Look up a PS Exception Log by its Salesforce record ID. Returns
    exception type, severity, location, and error message.

    Args:
        log_id: Salesforce PS Exception Log ID (starts with 'a1W').
    """
    return _get_exception_log(log_id)


@tool
def search_exception_logs(application: str = "", location: str = "") -> dict:
    """Search PS Exception Logs by application name and/or exception location
    (class name). Use to find related exceptions when you know the application
    or error location.

    Args:
        application: Application name (e.g., 'CCSP').
        location: Exception location / class name (e.g., 'CCSP_IP_GetRatesFlyoutInfo').
    """
    return _search_exceptions(application=application, location=location)


@tool
def classify_issue(description: str, error_data: str = "") -> dict:
    """Classify an issue based on the agent's description text and any error
    data gathered from log lookups. Returns category (LATENCY, UI_ERROR,
    AUTH_ERROR, DATA_ERROR, UNKNOWN), confidence score, and whether recording
    review is needed.

    Args:
        description: Agent-entered description of the issue.
        error_data: Error data gathered from log lookups (optional).
    """
    return _classify_issue(description, error_data)


@tool
def query_datadog_events(lan_id: str, trigger_time: str, lookback_minutes: int = 1440) -> dict:
    """Query Datadog for user events and clicks within a time window before
    the trigger time. Returns sequence of user interactions to help identify
    the cause of failure.

    Args:
        lan_id: User LAN ID to filter events.
        trigger_time: Trigger timestamp (ISO 8601 format).
        lookback_minutes: Minutes to look back from trigger time (default: 5).
    """
    try:
        # Get Datadog credentials
        credentials = get_datadog_credentials()
        api_key = credentials['api_key']
        app_key = credentials['application_key']
        endpoint = credentials['endpoint']
        
        # Parse trigger time
        trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
        start_dt = trigger_dt - timedelta(minutes=lookback_minutes)
        
        # Convert to Unix timestamps (seconds)
        start_ts = int(start_dt.timestamp())
        end_ts = int(trigger_dt.timestamp())
        
        log.info(f"Querying Datadog for lan_id={lan_id} from {start_dt} to {trigger_dt}")
        
        # Use httpx to query Datadog API directly
        import httpx
        
        headers = {
            'DD-API-KEY': api_key,
            'DD-APPLICATION-KEY': app_key,
            'Content-Type': 'application/json'
        }
        
        # Query for events
        query = f'@usr.lan_id:{lan_id}'
        params = {
            'filter[from]': start_ts,
            'filter[to]': end_ts,
            'filter[query]': query,
            'page[limit]': 1000
        }
        
        # Use the full endpoint URL from credentials
        events_url = endpoint
        
        with httpx.Client() as client:
            response = client.get(events_url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            events = data.get('data', [])
            
            log.info(f"Retrieved {len(events)} events from Datadog")
            
            # Extract relevant event details
            event_sequence = []
            for event in events:
                attributes = event.get('attributes', {})
                event_sequence.append({
                    'timestamp': attributes.get('timestamp'),
                    'message': attributes.get('message', ''),
                    'service': attributes.get('service', ''),
                    'status': attributes.get('status', ''),
                    'attributes': attributes.get('attributes', {})
                })
            
            return {
                'success': True,
                'lan_id': lan_id,
                'trigger_time': trigger_time,
                'lookback_minutes': lookback_minutes,
                'event_count': len(event_sequence),
                'events': event_sequence,
                'time_range': {
                    'start': start_dt.isoformat(),
                    'end': trigger_dt.isoformat()
                }
            }
            
    except Exception as e:
        log.error(f"Error querying Datadog: {e}")
        return {
            'success': False,
            'error': str(e),
            'lan_id': lan_id,
            'trigger_time': trigger_time
        }


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    parse_report,
    get_vlocity_log_by_id,
    search_vlocity_logs,
    get_exception_log_by_id,
    search_exception_logs,
    classify_issue,
    query_datadog_events,
]

_agent = None


def get_or_create_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            model=load_model(),
            system_prompt=_load_system_prompt(),
            tools=ALL_TOOLS,
        )
    return _agent


# ---------------------------------------------------------------------------
# AgentCore Runtime entrypoint
# ---------------------------------------------------------------------------

@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint. Receives report data and streams analysis."""
    log.info("Invoking One-Click Analysis Agent...")
    
    # Extract trigger time and lan_id from payload for Datadog query
    trigger_time = payload.get("datetime") or payload.get("trigger_time")
    lan_id = payload.get("user") or payload.get("lan_id")
    
    # Proactively fetch Datadog events if we have the required fields
    datadog_events = None
    if trigger_time and lan_id:
        log.info(f"Fetching Datadog events for user {lan_id} at {trigger_time}")
        try:
            # Get Datadog credentials
            credentials = get_datadog_credentials()
            api_key = credentials['api_key']
            app_key = credentials['application_key']
            endpoint = credentials['endpoint']
            
            # Parse trigger time
            trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
            start_dt = trigger_dt - timedelta(minutes=60)
            
            # Convert to Unix timestamps (seconds)
            start_ts = int(start_dt.timestamp())
            end_ts = int(trigger_dt.timestamp())
            
            log.info(f"Datadog query time range: {start_dt.isoformat()} to {trigger_dt.isoformat()}")
            log.info(f"Datadog timestamps: from={start_ts}, to={end_ts}")
            
            import httpx
            
            headers = {
                'DD-API-KEY': api_key,
                'DD-APPLICATION-KEY': app_key,
                'Content-Type': 'application/json'
            }
            
            # Query for logs - search for Vlocity error logs by user alias
            query = f'@data.payload.ChangeEventHeader.entityName:vlocity_cmt__VlocityErrorLogEntry__c @user_role.alias:{lan_id}'
            body = {
                'filter': {
                    'from': start_ts,
                    'to': end_ts,
                    'query': query
                },
                'page': {
                    'limit': 1000
                },
                'sort': 'desc'
            }
            
            log.info(f"Datadog API URL: {endpoint}")
            log.info(f"Datadog log query: {query}")
            log.info(f"Datadog request body: {json.dumps(body, indent=2)}")
            
            with httpx.Client() as client:
                response = client.post(endpoint, headers=headers, json=body, timeout=30.0)
                
                log.info(f"Datadog response status: {response.status_code}")
                log.info(f"Datadog response headers: {dict(response.headers)}")
                
                response.raise_for_status()
                
                data = response.json()
                log.info(f"Datadog raw response: {json.dumps(data, indent=2)}")
                
                events = data.get('data', [])
                
                log.info(f"Retrieved {len(events)} events from Datadog")
                log.info(f"Total response keys: {list(data.keys())}")
                
                # Extract relevant event details
                event_sequence = []
                for event in events:
                    attributes = event.get('attributes', {})
                    event_sequence.append({
                        'timestamp': attributes.get('timestamp'),
                        'message': attributes.get('message', ''),
                        'service': attributes.get('service', ''),
                        'status': attributes.get('status', ''),
                        'attributes': attributes.get('attributes', {})
                    })
                
                datadog_events = {
                    'success': True,
                    'event_count': len(event_sequence),
                    'events': event_sequence,
                    'time_range': {
                        'start': start_dt.isoformat(),
                        'end': trigger_dt.isoformat()
                    }
                }
        except Exception as e:
            log.error(f"Error fetching Datadog events: {e}")
            datadog_events = {
                'success': False,
                'error': str(e)
            }
    
    agent = get_or_create_agent()
    
    prompt = payload.get("prompt", "")
    if not prompt:
        # If raw report data is passed, wrap it in an analysis prompt
        report_data = {k: v for k, v in payload.items() if k != "prompt"}
        
        # Include Datadog events in the report data if available
        if datadog_events:
            report_data['datadog_events'] = datadog_events
        
        prompt = (
            "Analyze the following One-Click Report entry and provide a full "
            "root cause analysis.\n\n"
            f"Report Data:\n{json.dumps(report_data, indent=2)}"
        )

    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
