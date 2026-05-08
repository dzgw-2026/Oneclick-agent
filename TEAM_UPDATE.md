**One-Click Agent — S3 + DynamoDB updates pushed (agent 422)**

Implemented the items from yesterday's MOMs:

**S3 — new per-RecordID artifacts**
Each agent invocation now writes 3 JSON files to `s3://<bucket>/<recordid>/`:
- `raw_data.json` — original One-Click report payload
- `session_log_data.json` — last 10 min of Datadog records for the LAN ID (always fetched, even when an error message is present)
- `analysis_results.json` — Bedrock root-cause analysis (parsed JSON)

If `recordid` is missing, prefix falls back to `<user>_<datetime>`.

**DynamoDB — schema changes**
- New column `ErrorCode` (String) — sourced from the matched Datadog log, falls back to the agent's JSON output
- `RootCause` changed from String → **Map (JSON object)** — only the structured JSON is stored now, not free text
- No table migration needed (DynamoDB is schemaless for non-key attrs); existing rows untouched, new rows write the new shape

**Reliability**
S3 and DynamoDB writes are both wrapped — failures only log to CloudWatch, the streamed response to the caller is never interrupted.

**Needed before deploy:**
1. Confirm the S3 bucket name we should use → set `ONECLICK_S3_BUCKET` env var on the AgentCore Runtime
2. Add `s3:PutObject` permission to the agent's IAM role for that bucket
3. FYI for downstream consumers: if anything reads `RootCause` from DynamoDB, it now needs to handle Map type instead of String

Pure-Python helpers (JSON extraction, error-code derivation, prefix building) all unit-tested locally ✅. Doing the live AWS smoke test in the morning, then ready to deploy.
