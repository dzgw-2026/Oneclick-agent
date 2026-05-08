"""Query Datadog for Mulesoft logs using Correlation/Context IDs."""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

async def query_mulesoft_logs(ctx_id: str, trigger_time: str, credentials: dict) -> dict:
    """Queries Datadog for Mulesoft logs matching the context/correlation ID."""
    if not ctx_id:
        return {"success": False, "error": "No context ID provided"}

    t0 = time.monotonic()
    api_key = credentials['api_key']
    app_key = credentials['application_key']
    endpoint = credentials['endpoint']

    headers = {
        'DD-API-KEY': api_key,
        'DD-APPLICATION-KEY': app_key,
        'Content-Type': 'application/json'
    }

    # Define time window around the trigger time
    # Expand lookback and lookforward to handle timezone offsets and indexing delays
    try:
        trigger_dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        trigger_dt = datetime.now()
        
    start_dt = trigger_dt - timedelta(hours=12)
    end_dt = trigger_dt + timedelta(hours=12) 
    
    # Query for the specific context ID across Mulesoft services
    query = f"service:mulesoft* (@correlation_id:*{ctx_id}* OR @ctx_id:*{ctx_id}* OR @correlationId:*{ctx_id}* OR \"{ctx_id}\")"

    logger.info(f"Querying Datadog for Mulesoft logs: ctx_id={ctx_id}")
    logger.info(f"Time window: {start_dt.isoformat()} to {end_dt.isoformat()}")
    logger.info(f"Query string: {query}")

    body = {
        'filter': {
            'from': start_dt.isoformat(),
            'to': end_dt.isoformat(),
            'query': query,
        },
        'sort': 'timestamp',
        'page': {'limit': 50},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, headers=headers, json=body, timeout=30.0)

            # Log status and rate-limit headers for diagnostics regardless of outcome.
            rl_limit = response.headers.get("x-ratelimit-limit", "-")
            rl_remaining = response.headers.get("x-ratelimit-remaining", "-")
            rl_reset = response.headers.get("x-ratelimit-reset", "-")
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if response.status_code == 429:
                logger.error(
                    "query_mulesoft_logs -> 429 THROTTLED | ctx_id=%s elapsed=%dms "
                    "x-ratelimit-limit=%s remaining=%s reset=%s",
                    ctx_id, elapsed_ms, rl_limit, rl_remaining, rl_reset,
                )
                return {
                    "success": False,
                    "error": "Datadog rate limit (429)",
                    "status": 429,
                    "ctx_id": ctx_id,
                    "ratelimit_reset": rl_reset,
                }

            if response.status_code >= 400:
                logger.error(
                    "query_mulesoft_logs -> HTTP %d | ctx_id=%s elapsed=%dms "
                    "x-ratelimit-limit=%s remaining=%s reset=%s body=%s",
                    response.status_code, ctx_id, elapsed_ms,
                    rl_limit, rl_remaining, rl_reset,
                    response.text[:500],
                )
                return {
                    "success": False,
                    "error": f"Datadog HTTP {response.status_code}",
                    "status": response.status_code,
                    "ctx_id": ctx_id,
                }

            data = response.json()
            events = data.get('data', [])
            
            logger.info(
                "query_mulesoft_logs -> 200 | ctx_id=%s events=%d elapsed=%dms "
                "x-ratelimit-limit=%s remaining=%s reset=%s",
                ctx_id, len(events), elapsed_ms, rl_limit, rl_remaining, rl_reset,
            )
            
            logs = []
            for event in events:
                # Handle both internal and flattened attribute structures
                root_attrs = event.get("attributes", {})
                inner_attrs = root_attrs.get("attributes", {})
                
                logs.append({
                    "timestamp": root_attrs.get("timestamp"),
                    "message": root_attrs.get("message"),
                    "service": root_attrs.get("service"),
                    "correlation_id": inner_attrs.get("correlationId") or inner_attrs.get("correlation_id") or ctx_id
                })
                
            return {"success": True, "ctx_id": ctx_id, "logs": logs}

    except httpx.HTTPStatusError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "query_mulesoft_logs HTTPStatusError: status=%d ctx_id=%s elapsed=%dms error=%s",
            e.response.status_code, ctx_id, elapsed_ms, e,
        )
        return {"success": False, "error": str(e), "status": e.response.status_code, "ctx_id": ctx_id}
    except httpx.RequestError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "query_mulesoft_logs RequestError: ctx_id=%s elapsed=%dms error=%s",
            ctx_id, elapsed_ms, e,
        )
        return {"success": False, "error": str(e), "ctx_id": ctx_id}
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "query_mulesoft_logs unexpected error: ctx_id=%s elapsed=%dms %s: %s",
            ctx_id, elapsed_ms, type(e).__name__, e,
        )
        return {"success": False, "error": str(e), "ctx_id": ctx_id}
