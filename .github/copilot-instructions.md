# STYL project testing instructions

- When asked to perform regression testing or comprehensive/release verification,
  use the [styl-regression skill](skills/styl-regression/SKILL.md) and the
  [living regression plan](../docs/regression-test-plan.md).
  Default to the full active plan and all configured automated suites/browser
  projects, not only the latest changed feature. An explicitly narrower user
  request takes precedence and must be reported as targeted.
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
