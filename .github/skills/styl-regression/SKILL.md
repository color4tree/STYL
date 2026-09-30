---
name: styl-regression
description: Run STYL's full system, admin, and customer regression plan when asked for regression testing, a full regression, or release verification. Also use when adding or changing a STYL feature, function, enhancement, or bug fix to maintain the living regression plan and automated coverage. Account for desktop, mobile, API, persistence, privacy, and operational checks; never report blocked manual checks as passed.
---

# STYL regression and coverage maintenance

## Source of truth

Read the current files rather than relying on remembered test counts or earlier
requirements:

1. [Living regression test plan](../../../docs/regression-test-plan.md).
2. [Current behavior and test setup](../../../README.md).
3. [Project history and run summaries](../../../docs/project-history.md).
4. [Frontend scripts](../../../frontend/package.json) and
   [Playwright projects/server configuration](../../../frontend/playwright.config.ts).
5. [Backend requirements](../../../backend/requirements.txt).

For affected areas, also read the
[responsive design](../../../docs/mobile-ux-design.md),
[GeoIP guidance](../../../docs/geoip-pricing.md), and
[deployment guide](../../../docs/lightsail-deployment.md).
The [target schema](../../../docs/catalog-and-admin-schema-design.md) contains
future work, not a claim that all those features exist today.

## Choose the workflow

Use the [efficient-delivery skill](../styl-efficient-delivery/SKILL.md) to select
the initial scope and fail fast while developing. A plain request to implement,
push or deploy is not automatically comprehensive regression; shared/high-risk
changes and explicit full/comprehensive verification still require the full
baseline and applicable plan checks. Follow the living plan's run-selection policy.

### Full regression

Use this mode when the user asks to "do regression", "run regression", "regression
test", "full regression", or equivalent comprehensive/release verification.

**Default to the full active plan, not just the files changed most recently.**
Do not substitute a smoke test or one successful browser journey. If the user
explicitly requests a narrower scope, honor it and label the result targeted.

### Feature or bug-fix coverage maintenance

Use this mode whenever implementing a new feature, function, enhancement, or bug
fix, even if the user does not explicitly mention testing.

Update the plan and executable tests as part of the change. Run the smallest
meaningful validation during implementation, initially in one relevant browser
with `--max-failures=1` for Playwright. After that case is stable, run affected
configured browser projects and direct downstream checks. Run the full-regression mode when
explicitly requested or required for the agreed release verification.
Creating or editing this skill is not itself an instruction to launch a full
application regression.

## Workflow A: full regression

### 1. Identify the exact candidate and protect the workspace

- Inspect Git status, current commit, staged/unstaged changes, and relevant
  untracked source/tests.
- Record the commit plus a reviewed patch identifier if the tree is dirty.
  Do not call an uncommitted candidate tested merely by quoting its base commit.
- Preserve unrelated edits and local catalog data. In particular, do not assume an
  untracked hero configuration is approved for commit or fixture use.
- Verify test prerequisites from the current manifests and runner config.
  Install/restore only after manifest changes or a missing-dependency failure.
- Use only isolated test data and ephemeral test credentials. Never repoint the
  E2E runner at production. Do not change real prices/statuses to make tests pass.
- Check required ports and services. Do not terminate unrelated processes.

### 2. Account for every active case

Use the plan's stable IDs and build a run matrix with one of:

- Pass
- Fail
- Blocked
- Not run
- Not applicable, with a reason

Coverage labels A/P/M/F are not outcomes:

- Execute existing automated cases.
- Complete remaining portions of partially automated cases with additional
  automation or safe browser/system checks.
- Execute manual and operational checks when the environment, permissions, and
  devices are available.
- If a physical device, live GeoIP database, staging access, mail approval, or
  other prerequisite is missing, record Blocked and explain what is needed.
- Future-schema cases remain future/not applicable until implemented; do not
  count them as passing or treat them as current functionality.

Map each automated test result to the plan; do not count every clause in a plan
row as verified because one nearby test passed. Report both automated execution
counts and case-level coverage, including unresolved manual portions.

### 3. Execute the complete automated baseline

Use the repository's current runners and all configured browser projects. Do not
hard-code test counts or select Chromium only if additional projects are configured.

Current PowerShell commands, from the repository root:

```powershell
Push-Location backend
try {
    ..\.venv\Scripts\python.exe -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw "Backend regression failed." }
} finally {
    Pop-Location
}

npm --prefix frontend test
if ($LASTEXITCODE -ne 0) { throw "Frontend unit regression failed." }

npm --prefix frontend run lint
if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }

npm --prefix frontend run test:e2e
if ($LASTEXITCODE -ne 0) { throw "End-to-end regression failed." }
```

Adapt the Python executable to the project's configured environment when needed.
The current E2E harness builds the production frontend, including TypeScript
checking, and starts a real isolated API. Avoid a redundant production build when
that step already ran successfully. Re-read the config if this changes.

Do not silently skip a failed suite. A failed prerequisite means the affected
checks are blocked; diagnose it and resume the intended full run.

### 4. Verify system and end-user evidence

Follow the plan, including:

- Server validation, persistence, public/private response boundaries, regional
  prices, missing-price visibility, and draft controls.
- Actual admin create/edit/save/reload, error retention, dates, uploads, and
  independent public/internal fields.
- Customer navigation, galleries, cart quantities/current prices, and inquiry
  submission/recovery.
- Desktop and mobile layouts, threshold boundaries, keyboard/touch behavior, and
  the configured timezone/browser matrix.
- Operational GeoIP/proxy/cache, restart, backup/restore, real media, and mailbox
  checks when authorized and available.

Mocks demonstrate the mocked layer only:

- Canadian browser response fixtures do not certify real IP location.
- Offline MMDB-reader tests do not certify the installed live database/proxy.
- Mocked SMTP does not prove inbox delivery.
- WebKit/phone emulation does not certify a physical iPhone.

Do not invent access, send real customer information to external services, perform
destructive production tests, or bypass authorization to complete the matrix.

### 5. Diagnose and fix failures

- Inspect assertion/response, browser screenshot/trace, logs, and the data path.
- Distinguish product bugs, bad selectors/fixtures, asynchronous navigation
  assumptions, and environment failures.
- Reproduce a bug before fixing where feasible. Do not claim an unreproduced
  report Fixed; record the exact successful/unsuccessful reproduction attempts.
- Add or tighten the regression assertion that would have caught the problem.
- Fix the cause; do not weaken assertions, force clicks past disabled controls,
  add arbitrary sleeps, or enable retries to hide failures.
- Use targeted reruns while diagnosing, then rerun the complete automated baseline
  against the final candidate before calling that baseline a full pass.
- Repeat affected manual checks after changes. Do not combine incompatible
  results from different builds into one clean report.

### 6. Record and report

Use the run-record template in the plan. Record:

- Candidate/config, dates, runtime/browser/device versions, timezone/locale.
- Commands, exit codes, actual counts, case IDs and outcomes.
- Which dependencies/services were real or mocked.
- Failures found, fixes, rerun evidence, warnings, and exceptions.
- Unavailable manual/production checks and their prerequisites.
- Private artifact location and cleanup status.

Append a concise dated result to project history and keep the plan's evidence
current. Store detailed test artifacts in ignored/private locations, not committed
traces containing tokens or private form data.

Final report must distinguish:

1. Full automated code regression: passed/failed/blocked.
2. Active plan coverage: completed and incomplete case IDs/portions.
3. Production/physical-device readiness: verified or not verified.

Do not say "everything passes" while applicable checks remain blocked or unrun.
Commit, push, deployment, real email sends, and destructive staging operations
require the appropriate user authorization; a regression request does not imply them.

## Workflow B: keep coverage growing with each change

Before implementation:

1. Read the latest behavior oracle in the plan and the user's current requirement.
2. Identify existing affected cases at both system and end-user levels.
3. For a bug, capture the failing path when possible. For an enhancement, define
   success, invalid-input, missing-data, boundary, privacy, and compatibility cases.

During implementation:

4. Add executable tests in the existing backend, unit, or E2E runners. Reuse helpers
   and fixtures; do not create a parallel test framework.
5. Add new stable plan IDs where new behavior is not already covered. Otherwise
   update the existing case without changing its identity.
6. Use the plan's case template: priority, prerequisites, steps, expected UI/API/
   persistence results, environment, coverage type, test source, and cleanup.
7. Include the case ID in new automated test titles or an adjacent mapping comment
   where practical. Update the automation map and bug/enhancement traceability.
8. Include desktop/mobile, market, timezone, old-record, and failure-recovery
   variants when relevant, not merely the happy path.

Before declaring the change complete:

9. Run the relevant tests and report actual results.
10. Update directly affected behavior/design documentation.
11. If approved behavior replaces an old expectation, document that replacement
    and its new case IDs. Do not preserve contradictory tests or silently erase
    the old decision.
12. Mark unautomated requirements P/M with concrete remaining steps; never pretend
    documentation alone is executable coverage.
13. Keep planned schema features separate until implemented.

## Completion checklist

- [ ] Latest requirements and current plan read.
- [ ] Exact candidate identified; unrelated work preserved.
- [ ] Every active case accounted for when running full regression.
- [ ] Required automated suites/projects executed and final candidate verified.
- [ ] System and end-user assertions both covered.
- [ ] New/changed behavior represented in the plan and tests.
- [ ] Failures and unreproduced reports described accurately.
- [ ] Manual/operational gaps explicitly listed.
- [ ] Run record/history updated without secrets.
- [ ] Test fixtures/services cleaned up safely.
- [ ] No unauthorized commit, push, deployment, or production-data mutation.
