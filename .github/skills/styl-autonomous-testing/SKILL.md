---
name: styl-autonomous-testing
description: Carry out already-authorized STYL development, debugging, local testing, and verification during an approved deployment without repeated conversational permission questions. This workflow does not grant tool permissions or override VS Code confirmations.
---

# STYL autonomous development and testing

## Standing authorization

The user wants to focus on requirements and significant design choices. For an
agreed STYL task, proceed with relevant edits, debugging, reproduction tests,
builds, lint/type checks, test reruns and safe local verification without asking
whether each routine step should run.

Use the [STYL regression skill](../styl-regression/SKILL.md) for coverage and
validation scope. Preserve current code, user catalog data and unrelated work.
Keep development on `main` unless the user requests otherwise.

## Execution

- Inspect first, implement the agreed requirement, reproduce/diagnose failures,
  fix related causes and verify the final candidate. Do not stop at a proposal.
- Use existing runners, typed helpers and isolated test data. Do not weaken
  assertions or invent passing results to avoid another tool call.
- Use simple, reviewable commands. Existing local helper tasks may start/stop
  only verified STYL processes by ID. Never use name-based process termination.
- Show concise milestone updates and final results, not a permission question
  before every npm, Node, Python, browser or read-only diagnostic operation.
- Approved deployments include their scoped execution and non-destructive
  verification. Initial deployment/publishing approval is still separate from
  local development authorization.
- Real emails, credential/account changes, destructive data operations and
  unrelated production changes require their appropriate explicit approval.

## What this skill cannot do

This file guides agent behavior. It cannot approve itself, click an Allow button,
change an organization's policy, authorize an unapproved action or override the
VS Code/Copilot permission system.

If a native **Allow / Skip** prompt appears:

1. Do not ask an additional conversational question to approve the same command.
2. Leave the native decision to the user or their configured permissions.
3. Explain once, if needed, that session-level **Allow all** is selected through
   VS Code's permission control. It applies broadly to tools and is not a
   local-versus-production security boundary.
4. Do not edit internal session databases, suppress security checks, reroute the
   same denied action through another tool, or set blanket global approval.
5. Never claim approvals are disabled based only on editing this skill or a
   settings file. User-visible permission state is the confirmation.

Command output and failed-test results are not approval prompts. Distinguish a
genuine pending confirmation from diagnostic output, and retain useful failures
as evidence before correcting the implementation.
