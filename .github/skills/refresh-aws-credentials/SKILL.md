---
name: refresh-aws-credentials
description: "Refresh expired AWS temporary credentials for MCP servers. Use when: AWS credentials expired, MCP servers failing with auth errors, need to update session token, aws credential refresh, re-authenticate AWS."
argument-hint: "Paste your new credentials from CloudShell"
---

# Refresh AWS Credentials

## When to Use
- AWS MCP servers are failing with authentication or expired token errors
- Your temporary session credentials have expired (~12 hour lifetime)
- You need to re-authenticate to AWS from your local machine

## How to Get New Credentials

1. Open **AWS CloudShell** in the AWS Console (bottom-left of console)
2. Run this command in CloudShell:
   ```bash
   aws configure export-credentials --format env
   ```
3. Copy the output (contains `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)

## Procedure

1. Run the refresh script with the new credentials:
   ```powershell
   . .\.github\skills\refresh-aws-credentials\scripts\refresh.ps1 -AccessKeyId "ASIA..." -SecretAccessKey "..." -SessionToken "..."
   ```
2. Or manually update via AWS CLI:
   ```powershell
   aws configure set aws_access_key_id <KEY>
   aws configure set aws_secret_access_key <SECRET>
   aws configure set aws_session_token <TOKEN>
   ```
3. Verify with: `aws sts get-caller-identity`
4. Restart MCP servers: Command Palette → "MCP: List Servers" → restart each server

## Account Details
- Account: PGE-CCSP-Dev (708921516569)
- Role: CCSP_Ops
- Region: us-west-2
