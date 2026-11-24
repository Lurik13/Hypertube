---
name: fullstack-feature
description: "Use for planning and delivering a production full-stack feature across UX, frontend, API, domain, persistence, integrations, tests, and observability."
argument-hint: "Describe the feature and its user-visible outcome."
---
# Full-stack Feature Delivery

1. Define the user outcome, acceptance criteria, permissions, edge cases, and failure states.
2. Confirm UX flow and component/API/data contracts before implementation.
3. Implement a thin vertical slice through UI, application logic, domain rules, persistence, and integrations.
4. Add validation, authorization, structured errors, telemetry, migrations, and rollback considerations.
5. Add focused unit, contract, integration, end-to-end, accessibility, and performance checks as applicable.
6. Run the smallest relevant verification commands, then review the diff for security and consistency.

Report files changed, decisions, commands/results, and residual risks.
