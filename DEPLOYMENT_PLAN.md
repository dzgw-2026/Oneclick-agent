# OneClick Agent — AgentCore Runtime Deployment Plan

Everything in `us-west-2`. Do each step in order — don't skip ahead.

---

## Phase 1: Upload the Fixed Zip to S3

1. **Upload `oneclick-updated.zip`** from your desktop to S3:
   ```
   s3://a51k/OneClick-DataDog-AgentCore-Agent/oneclick-updated.zip
   ```
   Use the S3 console or CLI. Make sure you **overwrite** the old file, not upload alongside it.

2. **Verify the upload** — click "View" next to the S3 URI in the AgentCore console to confirm the file size is ~21 MB and the "Last modified" timestamp is fresh.

---

## Phase 2: Configure the AgentCore Runtime Agent

3. In the **Bedrock AgentCore console**, open your agent (`oneclick_analysis_agent`).

4. Confirm these settings:

   | Setting | Value |
   |---------|-------|
   | **S3 URI** | `s3://a51k/OneClick-DataDog-AgentCore-Agent/oneclick-updated.zip` |
   | **Agent entry point** | `main.py` |
   | **Python runtime** | `Python 3.13` |

5. **Check the agent's IAM execution role** — it needs these permissions:

   | Permission | Why |
   |------------|-----|
   | `bedrock:InvokeModel` on `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | Strands calls Claude via Bedrock |
   | `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan` on `VlocityErrorLogs` and `PSExceptionLogs` tables | The tools look up mock Salesforce data |
   | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | CloudWatch logging |

   If the role is missing DynamoDB or Bedrock permissions, add them now.

6. **Set environment variables** on the agent runtime (if the console supports it, or via the agent config):

   | Variable | Value |
   |----------|-------|
   | `VLOCITY_TABLE` | `VlocityErrorLogs` |
   | `EXCEPTION_TABLE` | `PSExceptionLogs` |

   *(These have defaults in the code, so this step is optional but explicit is better.)*

7. **Save and deploy** the agent. Wait until the status shows **ACTIVE** (not CREATING/UPDATING).

---

## Phase 3: Verify the Runtime Starts Clean

8. Go to **CloudWatch → Log Management → Log groups** →
   `/aws/bedrock-agentcore/runtimes/oneclick_analysis_agent-IkREAEHulm-DEFAULT`

9. **Look for a NEW log stream** with a timestamp AFTER your deployment (not the old ones from 11:55 or earlier).

10. In that new log stream, you should see **no errors** — specifically:
    - **No** `ModuleNotFoundError: No module named 'strands'` ← the old error
    - You should see uvicorn starting up on port 8080, and the app registering routes

    **If you still see the same error**, it means the runtime didn't pick up the new zip. Try:
    - Check the S3 object version matches
    - Create a **new version** of the agent (not just edit), or
    - Delete and recreate the agent pointing to the same S3 URI

---

## Phase 4: DynamoDB Tables + Mock Data

11. **Ensure the DynamoDB tables exist.** From the `terraform/` directory:
    ```bash
    cd terraform
    terraform init
    terraform apply -target=aws_dynamodb_table.vlocity_error_logs -target=aws_dynamodb_table.ps_exception_logs
    ```
    Or verify they already exist in the DynamoDB console.

12. **Seed mock data** (if not already done):
    ```bash
    terraform apply -target=null_resource.seed_vlocity_logs -target=null_resource.seed_exception_logs
    ```
    Or manually run:
    ```python
    import json, boto3
    table = boto3.resource('dynamodb', region_name='us-west-2').Table('VlocityErrorLogs')
    with open('mock_data/vlocity_error_logs.json') as f:
        items = json.load(f)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    ```
    Repeat for `PSExceptionLogs` with `ps_exception_logs.json`.

---

## Phase 5: Intake Lambda + API Gateway

13. **Get the Agent Runtime ARN/ID** from the AgentCore console. It looks like:
    ```
    arn:aws:bedrock-agentcore:us-west-2:ACCOUNT_ID:runtime/RUNTIME_ID
    ```

14. **Set it in Terraform** — create `terraform/terraform.tfvars`:
    ```hcl
    agent_runtime_id = "arn:aws:bedrock-agentcore:us-west-2:YOUR_ACCOUNT:runtime/YOUR_RUNTIME_ID"
    aws_region       = "us-west-2"
    ```

15. **Deploy everything:**
    ```bash
    cd terraform
    terraform apply
    ```

16. **Grab the outputs:**
    ```bash
    terraform output api_endpoint
    terraform output lambda_function_url
    ```

---

## Phase 6: Test End-to-End

17. **Send a test request:**
    ```bash
    curl -X POST YOUR_API_ENDPOINT \
      -H "Content-Type: application/json" \
      -d '{
        "user": "jsmith",
        "datetime": "2025-07-14T12:30:00Z",
        "processidentifier": "cCSPCreateServiceRequestEnglish",
        "errormessage": "Error in OmniScript a9zAm000000PQR1IAO",
        "description": "Page was spinning and then got an error"
      }'
    ```

18. **Check CloudWatch for both:**
    - **Agent runtime logs** — Strands agent processing, tool calls, Claude responses
    - **Lambda logs** — Intake Lambda invoking AgentCore

19. **If you get a 200 with analysis text** — you're done, it's working.

---

## Troubleshooting Checklist

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'strands'` | Runtime didn't load new zip. Re-upload, or recreate agent. |
| `AccessDeniedException` on `InvokeModel` | Agent execution role missing `bedrock:InvokeModel` permission |
| `AccessDeniedException` on DynamoDB | Agent execution role missing `dynamodb:GetItem/Query/Scan` |
| `ResourceNotFoundException` on DynamoDB | Tables not created yet — run Phase 4 |
| Lambda returns 500 `invoke_agent_runtime` | `AGENT_RUNTIME_ID` env var not set, or agent not ACTIVE |
| Timeout | Lambda timeout too low (increase from 120s) or agent runtime still starting |

---

**Start with Phase 1. Don't skip to Phase 5 until you see clean logs in Phase 3.**
