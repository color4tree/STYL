---
name: styl-efficient-delivery
description: Use for STYL development, debugging, test selection and approved deployments to fail fast, choose verification by change impact, avoid redundant builds and probes, and report actual timing without weakening safety or explicit full-regression requests.
---

# STYL efficient delivery

## Purpose and companion workflows

Deliver verified work with less repetition, not less correctness. Apply this
workflow alongside:

- [Autonomous testing](../styl-autonomous-testing/SKILL.md) for authorization and
  safe local/deployment execution.
- [Regression coverage](../styl-regression/SKILL.md) for behavior oracles, stable
  case IDs, evidence and full-regression requirements.
- [The living plan's run-selection policy](../../../docs/regression-test-plan.md#6-when-to-run-which-regression-set).

This is persistent agent guidance, not a tool-permission override or an automated
guarantee. It does not configure CI, move the workspace, install credentials or
make build reuse safe by itself.

## 1. Choose the scope before running

Inspect the current diff, relevant requirements, test scripts and runner config.
Read the relevant documentation sections instead of repeatedly rereading unrelated
history. Record a short impact decision with the proposed verification scope:

| Change | Final verification floor |
| --- | --- |
| Documentation or skill only | Content, links and whitespace; existing documentation checks if available. No application suite merely because a skill changed |
| Isolated wording, styling or page-level layout | Affected navigation/layout cases at desktop/mobile boundaries, lint/type/build when runtime code changes. No unrelated backend suite |
| Bounded feature or bug fix | Relevant unit/API tests, persistence/failure cases where applicable, direct downstream consumers and affected configured browser projects |
| Shared or high-risk behavior | Full automated baseline on the final candidate, plus applicable operational checks; includes authentication, privacy, pricing, shared persistence, media deletion, backup/restore, email delivery, proxy trust and broad shared UI changes |
| Explicit full regression or comprehensive release verification | Full active plan and all configured suites/projects, as defined by the regression skill |

A plain push/deploy request does not automatically turn a low-risk copy change
into comprehensive regression. It still requires candidate validation, appropriate
backups/rollback preparation and live verification. Honor any explicitly agreed
release gate. Record why a bounded change is targeted or why shared impact requires
the full baseline; never downgrade a failed/high-risk case just to save time.

## 2. Fail fast while implementing

1. Use an existing test or add the smallest case proving the requirement.
2. Run that case in one relevant browser first, normally desktop Chromium. Start
   in the reported browser instead when diagnosing a browser-specific problem.
3. Stop on the first failure. For Playwright, pass `--max-failures=1` during this
   iteration; do not run the same known-broken assertion across every project.
4. Inspect its assertion, relevant response, console or private trace. Classify
   the failure as product, fixture/selector, readiness or environment.
5. Fix the cause, rerun the failed case and its directly affected cases, then
   execute the final scope chosen above.

Example using the existing runner from the repository root:

```powershell
npm --prefix frontend run test:e2e -- engineering.spec.ts --project=desktop-chromium --max-failures=1
```

The filename/project is an example, not a permanent test selection. Choose the
actual affected files and combine related selectors into one invocation. Re-read
the configured projects before the final run; one-browser iteration is not
desktop/mobile certification.

Do not disable assertions, force inaccessible controls, add arbitrary sleeps,
increase timeouts without evidence, or enable retries to manufacture passes.
Use actual readiness indicators and inspect lazy media only after bringing it
into view. Prefer existing sign-in/fixture helpers over ad-hoc session injection.

## 3. Avoid redundant work

- Batch coherent edits and independent reads. Delegate only substantial,
  independent work with clear file ownership; do not duplicate an agent's trace.
- Do not run a full suite before implementation just as a ritual, or after every
  small edit. Run a baseline first only when it answers a specific diagnostic need.
- Once the scoped final run passes, do not launch another unchanged full run
  without a stated reason. A subsequent material change invalidates the affected
  evidence; rerun its scope, and the full baseline if claiming a full final pass.
- The current E2E runner performs a production build/type check. Do not run a
  separate identical local build immediately before or after it.
- Do not skip the runner's build or reuse a server by assumption. Until guarded
  artifact reuse exists, use the current runner. Future reuse must match source,
  lockfile, toolchain and build-time environment, and retain fresh isolated API
  data and credentials. Never point tests at production or the valuable local
  catalog mirror.
- Do not increase workers until fixtures/services are isolated per worker.
  Run only one harness using its reserved ports; coordinate parent/agent runs.
  Avoid concurrent lint/build work that races test-output cleanup.
- If repeated attempts produce no new evidence, stop repeating the command.
  Change the diagnostic approach or report the specific prerequisite/blocker.
  Preserve useful failure evidence; a later retry is not proof the cause was fixed.
- For OneDrive/locking failures, inspect and clean only exact inactive generated
  targets. Do not repeatedly clear broad directories, reinstall dependencies or
  alter system settings as a shortcut.

## 4. Keep approved deployment scoped

- Reuse the validated candidate. Exclude local catalog edits, the private mirror,
  credentials and test artifacts from publishing.
- Use a reviewed repeatable deployment path. Prefer approved direct SSH/CI when
  available. Browser-console fallback should use short checked commands and a
  reviewed script, not large streams of fragile keyboard input.
- Prepare the required backup/rollback once per candidate. Take a fresh protected
  snapshot if legitimate production edits invalidate it; never overwrite those
  edits with an older snapshot to make a comparison pass.
- Restart only changed services: a frontend-only release normally restarts web,
  not API or mail timers. Runtime/dependency differences may justify a target-host
  build; do not describe that necessary build as an unchanged local duplicate.
- Verify deployed revision, affected live paths and preservation boundaries.
  Use non-destructive checks and preserve privacy choices. Real emails/inquiries
  and production content mutation are not ordinary smoke tests.
- Recheck only what cleanup or a changed environment could affect. Do not keep
  repeating the entire customer journey after unrelated documentation edits.

## 5. Make efficiency measurable

Record phase start/end or command durations where available: implementation,
focused tests, broader tests/build and deployment. Report actual counts, candidate,
failures and remaining gaps concisely. Do not invent percentages for unmeasured
time or promise a fixed completion time regardless of complexity.

Distinguish a clean full run, a targeted pass, and a full attempt interrupted by
an environment failure followed by a focused rerun. Physical devices, real GeoIP
and mailbox delivery remain separate claims.

Workspace relocation, SSH/CI setup, new credentials and approval-setting changes
are separate decisions. Do not perform them merely because they might be faster.
