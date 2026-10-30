---
name: full-project-audit
description: Implements the KYCo deterministic per-file audit workflow for full-codebase security, Ponytail minimalism, and performance reviews across any project.
---

# Universal Full-Project Deterministic Audit Workflow

Use this skill to execute thorough, multi-mode audits across any codebase without token exhaustion or missed files.

## 1. Core Principle
**"You define the scope, the audit harness ensures 100% coverage."**
Never ask an agent to "review the whole project" in a single massive prompt. Instead, break the codebase into explicit target file lists and review each file systematically against the defined mode criteria.

## 2. Audit Modes Reference
1. **`security-audit`**:
   - Multi-tenant data leaks and database authorization bypasses.
   - Authentication token validation and secret management (`.env`, private keys).
   - Sensitive document, PII, and financial data access boundaries.
2. **`ponytail-quality` (Anti-Slop)**:
   - CodeSlop patterns (dead imports, loose `any`, padding comments, useless try/catches, redundant `async`).
   - Strict adherence to the Ponytail 7-step decision ladder (YAGNI, platform native, minimal code).
3. **`frontend-audit`**:
   - State caching & query staleTime configuration.
   - Button double-click loading guards (`if (loading) return`).
   - Animation performance (no `backdrop-filter: blur` opacity animations).
   - Modals and drawers rendered via DOM portals.
4. **`backend-audit`**:
   - Race condition prevention and transaction atomicity.
   - Standard library utilization over unnecessary 3rd party modules.
   - Safe error handling without crashing runtime processes.

## 3. Execution & Remediation Workflow
1. **Scope Selection**: Identify explicit directory or file paths to audit.
2. **Deterministic Run**: Audit files sequentially against the chosen mode criteria.
3. **Issue Reporting**: Produce structured findings:
   - File & Line Number
   - Severity (`Critical` / `High` / `Medium` / `Low`)
   - Anti-Pattern / Vulnerability description
   - Surgical, minimal fix (following the Ponytail ladder)
4. **Targeted Remediation**: Apply clean, minimal fixes one file at a time.
