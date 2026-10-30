---
name: dependency-management
description: Strict criteria and evaluation checklist for adding, updating, or pruning third-party package dependencies across any programming language.
---

# Dependency Management & Anti-Bloat Skill

AI agents must follow this 7-step checklist before installing any new package or third-party dependency.

---

## 7-Step Dependency Evaluation Protocol

1. **Check Existing Capabilities:** Does the project already have a helper or installed dependency that can achieve this?
2. **Standard Library First:** Can standard language libraries (`fetch`, `crypto`, `http`, `path`, `json`, `regex`) solve this in 5–10 lines?
3. **Bundle Size & Overhead:** Inspect package weight via bundle analyzer or package registry. Reject bloated multi-megabyte packages for trivial utilities.
4. **Maintenance & Health:** Verify active maintenance, release cadence, and community adoption.
5. **Security & Vulnerabilities:** Run vulnerability checks (`npm audit`, `cargo audit`, `govulncheck`).
6. **License Compliance:** Ensure open-source compatibility (MIT, Apache 2.0, BSD, ISC).
7. **Justification:** If still necessary, explicitly document *why* the dependency is needed in the commit message or PR description.
