---
name: Backend Quality
description: "Use when implementing or reviewing APIs, services, domain logic, persistence, migrations, integrations, authentication, or authorization."
applyTo: ["**/api/**","**/server/**","**/backend/**","**/*controller*.*","**/*service*.*","**/*repository*.*"]
---
# Backend Quality

- Validate untrusted input at boundaries and enforce authorization server-side.
- Keep domain rules independent from transport and persistence details.
- Use explicit error semantics, timeouts, idempotency, and safe retries where applicable.
- Make migrations reversible or document an explicit recovery plan.
- Emit useful structured telemetry without logging secrets or sensitive data.
