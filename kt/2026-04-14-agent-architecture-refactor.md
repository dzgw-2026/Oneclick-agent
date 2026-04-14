# KT: Agent Architecture Refactor — Converse API + In-Process Tools

**Date:** 2026-04-14  
**Author:** dzgw  
**Status:** Final  

## Summary

Replaced the Bedrock Agent + 4 Lambda action-group architecture with a single Lambda that uses the Bedrock Converse API for a tool-use loop. All 6 tools execute in-process as Python functions. Cleaned up old files, wrote 40 unit tests, and updated all Terraform.

## What's In Progress

- [ ] Real Salesforce integration (`lambdas/shared/sf_client.py`, `SF_MODE=live`) — **unassigned**
  - Mock DynamoDB interface is working. Need SF credentials in Secrets Manager.

## What's Next

- API Gateway authentication (IAM auth or API key) before production
- Structured logging / X-Ray tracing for the tool-use loop
- Converse API streaming for partial analysis responses
- Token usage tracking and Bedrock cost alerts

---

## 1. What This Project Does

This is an AI-powered agent that analyzes "One-Click Reports" submitted by customer service agents in the CCSP (Customer Care Service Platform). When a CS agent encounters a problem in a Salesforce OmniScript flow, they submit a One-Click Report. This agent automatically:

1. Parses the report to extract structured data and Salesforce record IDs
2. Looks up relevant error logs (Vlocity Error Logs, PS Exception Logs)
3. Classifies the issue type (LATENCY, UI_ERROR, AUTH_ERROR, DATA_ERROR, etc.)
4. Produces a root-cause analysis with severity, recommended action, and whether a recording review is needed

## 2. Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────┐
│  API Gateway  │────▶│  Lambda      │────▶│  Bedrock Converse API (Claude)   │
│  POST /analyze│     │  handler.py  │◀────│  Tool-use loop                   │
└──────────────┘     │              │     └──────────────────────────────────┘
                      │  Tools run   │
                      │  in-process  │
                      │  ┌──────────┐│     ┌──────────────────┐
                      │  │ tools/   ││────▶│  DynamoDB Tables  │
                      │  └──────────┘│     │  (mock SF data)   │
                      └──────────────┘     └──────────────────┘
```

**Single-Lambda, in-process tool execution.** There are no separate Lambda functions for each tool. The agent Lambda uses the Bedrock Converse API to run a multi-turn tool-use loop. When Claude requests a tool call, the Lambda dispatches it to a Python function in the `tools/` package, sends the result back, and loops until Claude produces a final answer.

This replaced a previous design that used a Bedrock Agent resource with 4 separate Lambda action groups.

## 3. Repository Structure

```
lambdas/
  handler.py              # Lambda entrypoint — Converse API agent loop
  system_prompt.txt        # System prompt with workflow, domain knowledge, output format
  tools/
    __init__.py
    definitions.py         # Tool specs (names, descriptions, input schemas) for Converse API
    parse_report.py        # Extract structured data + Salesforce IDs from report
    classify_issue.py      # Rule-based issue classification
    query_vlocity_logs.py  # Vlocity Error Log lookup/search + enrichment
    query_exception_logs.py# PS Exception Log lookup/search
  shared/
    __init__.py
    models.py              # Shared data models
    sf_client.py           # DynamoDB-backed mock Salesforce client

terraform/
  main.tf                  # Provider config
  lambda.tf                # Single Lambda function + IAM role
  api_gateway.tf           # HTTP API Gateway (POST /analyze)
  dynamodb.tf              # Vlocity + Exception log tables, seed data
  bedrock.tf               # (empty — no Bedrock Agent resources needed)
  s3.tf                    # (empty — schema bucket no longer needed)
  variables.tf             # Config variables
  outputs.tf               # API endpoint, Lambda name, table names

tests/
  test_agent.py                   # Tests for the agent loop and Lambda handler
  test_tools_parse_report.py      # Tests for parse_report tool
  test_tools_classify_issue.py    # Tests for classify_issue tool
  test_tools_query_vlocity_logs.py    # Tests for Vlocity log tools
  test_tools_query_exception_logs.py  # Tests for exception log tools

mock_data/
  sample_oneclick_report.json     # Example One-Click Report input
  vlocity_error_logs.json         # Example Vlocity Error Log records
  ps_exception_logs.json          # Example PS Exception Log records
```

## 4. How the Agent Loop Works

File: `lambdas/handler.py`

1. **Request arrives** at `POST /analyze` with a JSON body containing report fields (`user`, `description`, `datetime`, `errormessage`, `processidentifier`).
2. **`handler()`** validates required fields (`user`, `description`), then calls `run_agent()`.
3. **`run_agent()`** loads the system prompt, builds the initial user message with the report data, and enters a loop (max 15 turns):
   - Calls `bedrock-runtime.converse()` with the message history, system prompt, and tool config.
   - If `stopReason == "end_turn"` → extracts the final text response and returns it.
   - If `stopReason == "tool_use"` → dispatches each requested tool via `TOOL_DISPATCH`, collects results, appends them as a user message, and loops.
4. **Response** is returned as `{ "analysis": "...", "session_id": "..." }`.

## 5. Tools

### parse_report
- **Purpose**: Extract structured data from the report. Identifies Salesforce record IDs embedded in error messages (Vlocity IDs start with `a9z`, Exception IDs start with `a1W`).
- **Input**: Report fields (`user`, `datetime`, `processidentifier`, `errormessage`, `description`)
- **Output**: Parsed fields + `vlocity_log_ids`, `exception_log_ids`, `has_direct_ids`

### get_vlocity_log_by_id
- **Purpose**: Look up a single Vlocity Error Log by Salesforce record ID.
- **Input**: `log_id` (string starting with `a9z`)
- **Output**: Enriched log with parsed HTTP request/response payloads, error details, response codes.
- **Data source**: DynamoDB `VlocityErrorLogs` table

### search_vlocity_logs
- **Purpose**: Search for Vlocity Error Logs by agent ID + time range (used when no direct IDs are found).
- **Input**: `user`, `start_time`, `end_time` (ISO 8601)
- **Output**: List of enriched logs matching the criteria
- **Data source**: DynamoDB `VlocityErrorLogs` table via `User-Datetime-index` GSI

### get_exception_log_by_id
- **Purpose**: Look up a PS Exception Log by Salesforce record ID.
- **Input**: `log_id` (string starting with `a1W`)
- **Output**: Exception record with type, severity, location, message
- **Data source**: DynamoDB `PSExceptionLogs` table

### search_exception_logs
- **Purpose**: Search PS Exception Logs by application name and/or exception location.
- **Input**: `application` (optional), `location` (optional)
- **Output**: List of matching exception records
- **Data source**: DynamoDB `PSExceptionLogs` table

### classify_issue
- **Purpose**: Rule-based classification of the issue from description text + error data.
- **Input**: `description` (required), `error_data` (optional)
- **Output**: `category`, `confidence`, `recording_review_needed`, `matched_keywords`
- **Categories**: LATENCY, UI_ERROR, AUTH_ERROR, DATA_ERROR, UNKNOWN

## 6. Data Layer

`lambdas/shared/sf_client.py` is a mock Salesforce client backed by DynamoDB. It exposes the same interface that a real Salesforce client would. The `SF_MODE` env var controls which backend to use (currently only `mock` is implemented).

**DynamoDB Tables:**

| Table | Hash Key | GSI | Purpose |
|-------|----------|-----|---------|
| `VlocityErrorLogs` | `Id` (S) | `User-Datetime-index` (User + Datetime) | Vlocity Error Log records |
| `PSExceptionLogs` | `Id` (S) | — | PS Exception Log records |

Terraform seeds both tables with mock data from `mock_data/` on first deploy.

## 7. Infrastructure (Terraform)

Everything is in `terraform/`. Key resources:

- **AWS Lambda** (`agent`): Single function, Python 3.12, 120s timeout, 256MB. Zips the entire `lambdas/` directory.
- **API Gateway** (HTTP API): `POST /analyze` route → Lambda proxy integration.
- **DynamoDB**: Two tables as described above.
- **IAM**: Lambda role with CloudWatch Logs, DynamoDB read, and `bedrock:InvokeModel` permissions.

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-west-2` | Deployment region |
| `bedrock_model_id` | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Claude model for the agent |
| `lambda_timeout` | `120` | Seconds — must accommodate multi-turn loop |
| `vlocity_table_name` | `VlocityErrorLogs` | DynamoDB table name |
| `exception_table_name` | `PSExceptionLogs` | DynamoDB table name |

### Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

The API endpoint is output as `api_endpoint`.

## 8. Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All tests mock DynamoDB and Bedrock calls — no AWS credentials needed. Test files:

- `test_agent.py` — Tests the Converse API agent loop (`run_agent`) and Lambda handler (`handler`). Mocks `boto3.client` for bedrock-runtime and validates tool dispatch, multi-turn behavior, error handling, and HTTP responses.
- `test_tools_parse_report.py` — Tests report parsing and Salesforce ID extraction.
- `test_tools_classify_issue.py` — Tests rule-based classification for all categories.
- `test_tools_query_vlocity_logs.py` — Tests log lookup, search, and HTTP payload enrichment.
- `test_tools_query_exception_logs.py` — Tests exception log lookup and search.

## 9. How the System Prompt Works

File: `lambdas/system_prompt.txt`

The system prompt defines a 5-step workflow the agent follows:

1. **Parse the report** → call `parse_report`
2. **Look up error logs** → call `get_vlocity_log_by_id` / `get_exception_log_by_id` (if IDs found) or `search_vlocity_logs` (if not)
3. **Check for linked exceptions** → if a Vlocity log has an `exception_log_id`, look that up too
4. **Classify the issue** → call `classify_issue`
5. **Produce analysis** → structured JSON + human-readable summary

The prompt includes domain knowledge about OmniScript process identifiers, common error patterns (HTTP 401/500 codes), Vlocity log structure, and the fact that ~80% of agent descriptions are too vague for root cause (flag `recording_review_needed`).

## 10. Example API Call

```bash
curl -X POST https://<api-endpoint>/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "user": "jsmith01",
    "datetime": "2025-03-15T10:30:00Z",
    "processidentifier": "cCSPCreateServiceRequestEnglish",
    "errormessage": "Error: Check Vlocity Error Log a9z000000000001 for details",
    "description": "SCREEN FROZE WHEN TRYING TO CREATE SR"
  }'
```

**Response:**
```json
{
  "analysis": "{ ... structured JSON analysis ... }\n\nThe agent experienced a screen freeze...",
  "session_id": "uuid"
}
```

## 11. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single Lambda + Converse API** instead of Bedrock Agent + action groups | Simpler to deploy, debug, and test. No agent/alias provisioning. Tool execution is faster (no cross-Lambda invocation). |
| **In-process tool dispatch** | Tools are pure Python functions — no network calls except to DynamoDB. Reduces latency and eliminates cold-start overhead of 4 extra Lambdas. |
| **120s Lambda timeout** | The Converse API loop can take multiple turns (up to 15). Each `bedrock:InvokeModel` call may take 5-15s. |
| **DynamoDB mock** | Simulates Salesforce data. `sf_client.py` interface is designed to be swapped to real Salesforce later. |
| **Rule-based classification** | `classify_issue` uses keyword matching, not an LLM call. Fast, deterministic, and easy to extend. |

## 12. Future Work / Open Items

- **Real Salesforce integration**: Replace mock DynamoDB client with actual Salesforce API calls (set `SF_MODE=live`)
- **Authentication**: API Gateway currently has no auth — add IAM auth or API key before production
- **Observability**: Add structured logging / X-Ray tracing for the tool-use loop
- **Streaming**: Converse API supports streaming responses — could stream partial analysis back
- **Cost controls**: Add token usage tracking and budget alerts for Bedrock invocations
