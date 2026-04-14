# KT Document Standards

**Team:** Ratnadeep, dzgw  
**Project:** One-Click Report Analysis Agent

---

## Purpose

Every KT (Knowledge Transfer) document captures the current state of a workstream so that any team member can pick it up, understand what's been done, what's in progress, and what's next — without needing a live walkthrough.

## When to Write a KT

- After completing a significant milestone or feature
- Before handing off work to the other team member
- When a major architectural decision is made
- At the end of a sprint or work cycle
- When onboarding someone new to the project or a specific area

## File Naming

```
kt/YYYY-MM-DD-<short-topic>.md
```

Examples:
- `kt/2026-04-14-agent-architecture-refactor.md`
- `kt/2026-04-18-dynamo-to-salesforce-migration.md`
- `kt/2026-04-22-api-auth-implementation.md`

## Required Sections

Every KT doc must include these sections in order:

### 1. Header

```markdown
# KT: <Title>
**Date:** YYYY-MM-DD  
**Author:** <name>  
**Status:** Draft | Final  
```

### 2. Summary (2-3 sentences)

What this KT covers at a glance. A team member should know whether this doc is relevant to them after reading this.

### 3. What Was Done

Bullet list of completed work. Be specific — reference file paths, tool names, resource names. Include the *why* behind non-obvious decisions.

Example:
```markdown
- Replaced Bedrock Agent + 4 Lambda action groups with single Lambda using Converse API (`lambdas/handler.py`)
  - Why: Simpler deployment, faster tool execution, easier to test
- Added `classify_issue` tool with rule-based keyword matching (`lambdas/tools/classify_issue.py`)
- Wrote 40 unit tests covering all tools and the agent loop (`tests/`)
```

### 4. What's In Progress

Work that is started but not yet complete. Include:
- What's being worked on
- Who is working on it
- Current status / blockers
- Where the code lives (branch, files)

Example:
```markdown
- [ ] Real Salesforce integration for sf_client.py — **Ratnadeep**
  - Interface designed, mock working. Need SF credentials in Secrets Manager.
  - Blocked on: waiting for CCSP team to provision connected app
```

### 5. What's Next

Planned work that hasn't started yet, in rough priority order.

### 6. Architecture / Technical Details

Include as much or as little as the topic requires:
- Diagrams (ASCII or Mermaid)
- File structure
- Data flow
- API contracts
- Key config / environment variables

### 7. How to Test / Verify

Commands to run, endpoints to hit, or manual steps to verify the work described in this KT.

### 8. Open Questions / Decisions Needed

Anything unresolved that the team needs to discuss or decide on.

---

## Best Practices

- **Be concrete.** File paths, function names, resource names — not vague descriptions.
- **Explain the why.** Decisions aren't obvious 2 weeks later. A single sentence of rationale saves hours.
- **Keep it current.** Update "What's In Progress" as things move. A stale KT is worse than no KT.
- **One topic per doc.** Don't cram unrelated work into one KT. Write a new one.
- **Link, don't duplicate.** If another KT covers something, link to it instead of repeating.
- **Track ownership.** Always note who did or is doing the work. "We" is ambiguous with 2+ people.
- **Include test evidence.** Paste the test output or a curl command. Proof it works > "it should work."

## Template

A blank template is at [kt/TEMPLATE.md](TEMPLATE.md). Copy it when starting a new KT.
