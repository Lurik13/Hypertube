# GitHub Copilot Instructions (Full-stack product workspace)

This repository is preparing a production-grade modular web application. Keep
the architecture stack-agnostic until the architecture workflow records an
explicit decision.

## 1. Core Engineering Principles
- **First-Principles Architecture:** Prioritize modularity, loose coupling, and clean separation of concerns. Do not introduce monolithic hacks or shortcuts.
- **Defensive Engineering & Root-Cause Analysis:** When debugging or implementing fixes, isolate the root cause empirically. Explicitly flag potential side-effects, concurrency issues, or architectural debt before writing code.
- **Type Safety & Rigor:** Enforce strict typing, explicit error handling, and robust input validation across all languages. Never suppress compiler warnings or static analysis errors with blind casts or ignores.

## 2. Multi-Agent Hierarchy & Subagent Communication Protocol
- **Chain of Command:** Subagents do not operate in silos. Every subagent (whether assigned to coding, testing, or documentation) must report its findings, architectural decisions, and blockers directly back to the parent/orchestrator agent or human reviewer.
- **Mandatory Documentation Trail:** Every subagent task execution must output a structured progress report or log update detailing:
  1. Files modified or created.
  2. Verification commands run and their outcomes.
  3. Any residual technical debt or security considerations.

## 3. Dependency, Framework & Security Verification Rule
- **Online Verification Check:** Before introducing any new framework, library, external package, or version upgrade, agents **must verify online/registry sources** (e.g., npm, PyPI, crates.io, GitHub Advisories) to confirm:
  - It is the latest stable version.
  - It has **zero known high or critical security vulnerabilities (CVEs)**.
- **Prohibition:** Never assume or hardcode outdated package versions. If a security advisory exists, reject the version immediately and select a patched release.

## 4. Code Style & Standards
- **Documentation:** Document all public APIs, complex algorithmic loops, and configuration schemas.
- **Containerization & Reproducibility:** Ensure all services and dependencies are fully containerized (Docker/Docker Compose) with deterministic builds.
- **Security First:** Never hardcode secrets, API keys, or credentials.

## 5. Product Development Workflow
- Start significant work by identifying user outcomes, constraints, assumptions,
  affected boundaries, and measurable acceptance criteria.
- Prefer vertical slices that connect UI, API, domain logic, persistence, and
  observability over disconnected layer-only implementations.
- Keep presentation, application orchestration, domain rules, infrastructure,
  and external integrations replaceable and testable.
- Treat accessibility, responsive behavior, performance budgets, failure states,
  and visual consistency as first-class requirements.
- Record material architecture choices, rejected alternatives, and consequences
  in decision records before implementation.
- Do not select a framework, package, cloud service, or database by habit.
  Compare viable options against explicit requirements and verify current
  security and maintenance status before adoption.

## 6. Specialist Reporting Contract
Every specialist or delegated agent must report:
1. Scope and assumptions.
2. Files created or modified.
3. Decisions, alternatives, and unresolved questions.
4. Verification commands and outcomes.
5. Security, accessibility, performance, or technical-debt considerations.
