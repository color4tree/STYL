# STYL project testing instructions

- Apply the [efficient-delivery skill](skills/styl-efficient-delivery/SKILL.md)
  to STYL development, debugging, test selection and approved deployments.
  Classify change impact first; iterate on the smallest relevant case in one
  browser with fail-fast enabled, then run the required final scope. Do not
  repeat unchanged builds/full suites or replace evidence with blind retries.
- Follow the [autonomous testing workflow](skills/styl-autonomous-testing/SKILL.md)
  for routine execution already authorized by the user. It avoids repeated
  conversational permission questions, but does not override native tool approvals.
- When asked to perform regression testing or comprehensive/release verification,
  use the [styl-regression skill](skills/styl-regression/SKILL.md) and the
  [living regression plan](../docs/regression-test-plan.md).
  Default to the full active plan and all configured automated suites/browser
  projects, not only the latest changed feature. An explicitly narrower user
  request takes precedence and must be reported as targeted.
- A plain push/deploy request is not itself a request for full-system regression.
  Use the [run-selection policy](../docs/regression-test-plan.md#6-when-to-run-which-regression-set):
  focused coverage for bounded low-risk changes, full coverage for shared/high-risk
  changes or an explicit full/comprehensive verification request. Keep backups,
  privacy/data protection and live verification mandatory for approved releases.
- When implementing any feature, function, enhancement, or bug fix, follow the
  skill's coverage-maintenance workflow: add/update relevant executable tests and
  stable plan cases, including system and end-user expectations. Maintain the
  automation map and bug/enhancement traceability.
- Do not interpret a request to create/edit this skill or documentation as a
  request to execute the application regression suite.
- Read current requirements before relying on historical decisions. The
  [target schema](../docs/catalog-and-admin-schema-design.md) includes future
  functionality; it is not all implemented.
- Use isolated fixture data. Preserve unrelated work and local catalog files.
  Never test destructive workflows against production without explicit approval.
- Report manual/operational checks as Blocked/Not run when prerequisites are
  unavailable. Automated passes do not certify physical phones, real GeoIP/proxy
  behavior, or mailbox delivery.
- Record the exact tested revision/patch, actual results, gaps, and a concise
  summary in [project history](../docs/project-history.md). Do not hard-code counts.
- Regression testing does not itself authorize committing, pushing, deploying,
  exposing private test artifacts, or changing real customer/catalog data.

## Development, testing and deployment verification authorization

- The user authorizes routine development and local testing for requested STYL
  work without repeated permission questions: inspect/edit relevant source,
  maintain tests/docs, run local builds/lint/type checks/isolated tests, debug,
  and inspect the app through localhost browser tools.
- This includes starting/restarting/stopping verified STYL loopback development
  servers by specific process ID, not unrelated processes or production services.
- The user prefers to focus on requirements and significant design decisions.
  Complete implementation/debugging, reproduce failures, run and rerun relevant
  tests, inspect results, and fix issues within the agreed scope without asking
  for permission at each step. Test output is evidence, not a request for input;
  report concise milestones and the final outcome rather than routine commands.
- Non-destructive verification of the STYL live site is authorized: public
  page/API requests, isolated browser sessions, screenshots and network traces
  without credential/customer-data disclosure. Do not send real inquiry emails,
  mutate production catalog/customer data, or expose private records as tests.
- Once the user explicitly approves a deployment, carry out its scoped backups,
  build/install, necessary service restarts and pre/post-deployment verification
  without repeatedly asking for conversational approval. Pause for an unexpected
  destructive operation, scope-changing decision, missing credential/access,
  or unresolved risk needing the user's decision.
- In this Windows Copilot session, use simple terminal invocations where possible.
  The runtime requires confirmation for inline PowerShell assignments/method
  calls even when the underlying commands are allowlisted. When the ignored
  `.vscode/local-dev.ps1` helper exists, use it for Inspect, Health, local
  Test/Lint/Build/E2E/Validate, and verified StopWeb/StopApi operations. Use the
  existing local VS Code tasks to start servers.
- For local Node/Playwright debugging, put reviewed temporary scripts under the
  ignored `.styl-runtime/dev/` folder and invoke them with a simple
  `node .styl-runtime\dev\name.cjs` command, instead of inline code or shell
  here-strings. Keep these scripts strictly local, use disposable browser/test
  state, and remove them when finished. Script-path approval is not a sandbox;
  do not use approved helpers/scripts to perform otherwise unauthorized actions.
- Use reasonable implementation choices within the agreed task. Ask about
  significant product/behavior changes or genuinely ambiguous requirements, not
  routine execution steps.
- Keep work on `main`, preserve unrelated edits and real catalog/customer data,
  and use disposable test fixtures with SMTP disabled. Restore dependencies only
  when the task needs it, after manifest changes or a missing-dependency failure.
- This standing authorization does not cover commits/pushes, backup-branch
  updates, initiating a deployment, unrelated AWS/production mutations, real
  emails, credential/account changes, destructive data operations, or exposing
  local services beyond loopback. Obtain explicit approval for those actions;
  an approved deployment includes the scoped execution/verification above.
- Workspace approval rules are a convenience, not a sandbox or a substitute for
  these scope limits. Do not bypass a remaining VS Code/organization confirmation.
- Session-wide Allow all must be selected by the user through VS Code's
  permission control or its supported slash command. It removes tool prompts,
  not the agreed scope limits; do not claim it is enabled merely because these
  instructions were edited or a configuration file was validated.
