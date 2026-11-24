---
name: testing-strategy
description: "Use for defining or executing a layered test strategy for frontend, backend, APIs, data, accessibility, visual regressions, performance, and release verification."
argument-hint: "Describe the behavior, feature, or release that needs verification."
---
# Testing Strategy

1. Convert requirements into observable acceptance criteria and risk-based test cases.
2. Select the smallest effective mix of unit, contract, integration, end-to-end, accessibility, visual, performance, and resilience tests.
3. Define deterministic fixtures, environment prerequisites, data cleanup, and test ownership.
4. Run focused checks first, then expand only when evidence requires it.
5. Report exact commands, outcomes, thresholds, coverage evidence, flaky behavior, and untested risks.

Do not substitute a passing proxy check for the required behavior.
