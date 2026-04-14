# Plan: One-Click Report Analysis Agent (AWS/Lambda/Bedrock)

## TL;DR
Build a single Lambda agent that uses the Bedrock Converse API (tool use) to analyse One-Click Reports. Reports arrive via API Gateway, the Lambda runs a multi-turn Converse loop with Claude calling in-process tools to parse report data, query Salesforce logs (mocked in DynamoDB), classify the issue, and produce a structured JSON + human-readable root-cause analysis. Infrastructure defined in Terraform, all code in Python.

## Architecture

```
POST /analyze
    │
    ▼
API Gateway (HTTP)
    │
    ▼
Agent Lambda ─── Bedrock Converse API (Claude 3.5 Sonnet)
    │                   │
    │          ┌────────┼──────────┬──────────────────┐
    │          ▼        ▼          ▼                  ▼
    │    parse_report  get/search  get/search     classify_issue
    │    (in-process)  vlocity     exception      (in-process)
    │                  logs        logs
    │                  (in-proc)   (in-proc)
    │                   │           │
    └──────────────────►▼───────────▼
                      DynamoDB (mock SF)
```

## Phase 1: Project Scaffolding & Mock Data

1. **Create project structure** — `lambdas/`, `lambdas/tools/`, `lambdas/shared/`, `terraform/`, `mock_data/`, `tests/`
2. **Build mock Salesforce data** — JSON files based on document screenshots (Vlocity Error Logs, PS Exception Logs, sample report rows)
3. **Define shared data models** — Pydantic models for `OneClickReport`, `VlocityErrorLog`, `PSExceptionLog`, `AnalysisResult`

## Phase 2: Tool Functions

4. **`tools/parse_report`** — Extract key fields, regex-extract Salesforce IDs from error messages
5. **`tools/query_vlocity_logs`** — Look up by ID or search by LAN ID + timeframe, parse HTTP payloads
6. **`tools/query_exception_logs`** — Look up PS Exception Logs by ID or search by app/location
7. **`tools/classify_issue`** — Rule-based categorization (LATENCY, UI_ERROR, AUTH_ERROR, DATA_ERROR, UNKNOWN) + flag recording_review_needed
8. **`tools/definitions`** — Converse API toolSpec definitions for all 6 tools

## Phase 3: Agent Handler (Converse API)

9. **`handler.py`** — API Gateway handler + Converse API tool-use loop
10. **`system_prompt.txt`** — System instructions for Claude (workflow, domain knowledge, output format)
11. **Tool dispatch** — Routes tool_use requests to local Python functions, returns results as toolResult

## Phase 4: Terraform Infrastructure

12. **Single Lambda** — packages entire `lambdas/` directory; IAM for DynamoDB read + bedrock:InvokeModel
13. **API Gateway** — `POST /analyze` → Lambda proxy
14. **DynamoDB** — VlocityErrorLogs + PSExceptionLogs tables with mock data seeding
15. **No Bedrock Agent resource** — Converse API used directly, no action groups / S3 schemas needed

## Phase 5: Testing & Validation

16. **Unit tests** — pytest for each tool function + handler validation + Converse loop mocking
17. **Integration test** — End-to-end POST → analysis response

## Key Files

| Path | Purpose |
|------|---------|
| `lambdas/handler.py` | API Gateway handler + Converse API agent loop |
| `lambdas/system_prompt.txt` | Agent system instructions |
| `lambdas/tools/definitions.py` | Converse API tool schemas (6 tools) |
| `lambdas/tools/parse_report.py` | Parse report + extract SF IDs |
| `lambdas/tools/query_vlocity_logs.py` | Query Vlocity Error Logs |
| `lambdas/tools/query_exception_logs.py` | Query PS Exception Logs |
| `lambdas/tools/classify_issue.py` | Categorise issue |
| `lambdas/shared/models.py` | Shared Pydantic data models |
| `lambdas/shared/sf_client.py` | Salesforce interface (mock → real via env var) |
| `mock_data/*.json` | Sample data from document screenshots |
| `terraform/*.tf` | Infrastructure |
| `tests/test_*.py` | Unit tests |
| `requirements.txt` | Python dependencies |

## Decisions

- **AgentCore / Converse API** — tools run in-process, no separate Lambdas or Bedrock Agent resource
- **Mock-first SF layer** — swap to real `simple-salesforce` + Secrets Manager later via env var
- **Bedrock model:** Claude 3.5 Sonnet (configurable via env/variable)
- **Terraform for IaC** — all .tf files ready to deploy
- **Python 3.12** throughout
- **DynamoDB** simulates SF query patterns
- **Scope exclusions:** No recording analysis, no SharePoint, no auth UI — API only

## Future Considerations

1. **Bedrock Knowledge Base** — OmniScript docs + known error patterns
2. **Batch processing** — S3 trigger → Step Functions for full Excel exports
3. **Real Salesforce** — Connected App OAuth in Secrets Manager
