# Engineering Certification Enablement Guide (SYNTHETIC)

> Source ID: KB-ENABLE-001 — approved internal study reference (fabricated for demo).

## Role-to-Certification Map

- **Cloud Engineer** — Primary: AZ-204, Secondary: AZ-305
- **DevOps Engineer** — Primary: AZ-400 (requires AZ-104 + AZ-204)
- **Data Engineer** — Primary: DP-203
- **Security Engineer** — Primary: AZ-500

## AZ-204 — Developing Solutions for Azure

### Domain: API Development (35% of exam)
APIs are exposed and managed through Azure API Management. Developers must understand
products, subscriptions, and policies. A **policy** in API Management transforms or
constrains a request/response as it flows through the gateway. Inbound policies run
before the backend is called; outbound policies run after.

### Domain: Azure Functions (30% of exam)
Azure Functions use **triggers** and **bindings**. A **trigger** is what causes a
function to run (for example an HTTP request or a queue message); a function has exactly
one trigger. **Bindings** are declarative connections to data; a binding can be an input
binding, an output binding, or both. A common misconception is confusing a trigger with
a binding — every trigger is conceptually a special binding, but not every binding is a
trigger, and a function may have many bindings but only one trigger.

### Domain: Storage (20% of exam)
Azure Blob Storage offers three access tiers: Hot, Cool, and Archive. Hot is optimized
for frequent access; Archive is lowest cost but requires rehydration before reading.

### Domain: Security (15% of exam)
Managed identities let an application authenticate to Azure services without storing
credentials in code. A **system-assigned** identity is tied to a single resource's
lifecycle; a **user-assigned** identity is a standalone resource that can be shared
across multiple services.

## Recommended Study Pattern
- 1–2 hours daily focused study
- Weekly assessment checkpoints
- Target **75% practice score** across **every** exam domain before sitting the exam
