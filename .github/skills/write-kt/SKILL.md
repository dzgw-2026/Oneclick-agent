---
name: write-kt
description: 'Write a KT (Knowledge Transfer) document. Use when: writing a KT, creating a knowledge transfer doc, documenting completed work, handing off a feature, recording architecture decisions, writing a status update for the team.'
argument-hint: 'Describe the topic or work to document (e.g., "agent architecture refactor", "Salesforce integration")'
---

# Write KT Document

Generate a KT (Knowledge Transfer) document following the team's standards.

## When to Use

- After completing a feature or milestone
- Before handing off work to another team member
- When a major architectural decision was made
- At the end of a sprint or work cycle
- When someone asks to "write a KT" or "document what was done"

## Procedure

### Step 1: Gather Context

1. Read the KT instructions and template:
   - [kt-instructions.md](./kt-instructions.md) — standards, required sections, best practices
   - [TEMPLATE.md](./TEMPLATE.md) — blank template
2. Read existing KT docs in `kt/` to understand what's already been documented and avoid duplication.
3. Explore the codebase to understand the current state of the work being documented. Look at:
   - Recent file changes and new files
   - Test files and test results
   - Terraform / infrastructure changes
   - Any TODO comments or open items

### Step 2: Ask Clarifying Questions

Use the ask-questions tool to confirm:
- **Topic**: What work is this KT covering?
- **Author**: Who wrote this KT? (Team members: Ratnadeep, Doug)
- **Status**: Draft or Final?
- **In-progress items**: Is anything still being worked on? By whom? Any blockers?
- **Open questions**: Anything the team still needs to decide?

Skip questions where the answer is obvious from context.

### Step 3: Write the Document

Create the file at:
```
kt/YYYY-MM-DD-<short-topic>.md
```

Use today's date. The short-topic should be lowercase, hyphen-separated, 3-5 words.

Follow this structure exactly:

```markdown
# KT: <Title>

**Date:** YYYY-MM-DD  
**Author:** <name>  
**Status:** Draft | Final  

## Summary
<!-- 2-3 sentences -->

## What Was Done
<!-- Bullet list with file paths, tool names, resource names. Include WHY for non-obvious decisions. -->

## What's In Progress
<!-- Checkbox list. Include who, status, blockers. -->

## What's Next
<!-- Planned work in priority order. -->

## Architecture / Technical Details
<!-- Diagrams, file structure, data flow, API contracts, config. As needed. -->

## How to Test / Verify
<!-- Commands, endpoints, manual steps. -->

## Open Questions / Decisions Needed
<!-- Anything unresolved. -->
```

### Step 4: Quality Check

Before finishing, verify:
- [ ] File is in `kt/` with `YYYY-MM-DD-<topic>.md` naming
- [ ] All 7 required sections are present (Summary through Open Questions)
- [ ] "What Was Done" references specific file paths and function names, not vague descriptions
- [ ] "What's In Progress" names who is doing the work
- [ ] Non-obvious decisions include a "Why:" explanation
- [ ] "How to Test" includes actual runnable commands or steps
- [ ] No duplication with existing KT docs — link instead of repeating

## Rules

- **Be concrete.** Reference `lambdas/handler.py`, not "the handler". Reference `classify_issue` tool, not "the classification logic".
- **Track ownership.** Every in-progress item must name who is working on it (Ratnadeep or Doug). Never use "we" for ownership.
- **One topic per KT.** If the work spans unrelated areas, write separate KT docs.
- **Include test evidence.** Paste pytest output or curl commands. "It should work" is not acceptable.
- **Explain the why.** A single sentence of rationale for each non-obvious decision.
