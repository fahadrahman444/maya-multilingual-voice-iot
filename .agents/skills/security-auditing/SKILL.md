---
name: security-auditing
description: Universal security guidelines, multi-tenant data isolation, JWT/Session auth verification, rate limiting, and input sanitization protocols for web and API backends.
---

# Universal Security & Auditing Guidelines

Use this skill when auditing, testing, or building backend endpoints, database policies, authentication routines, or file upload/verification flows.

## 1. Multi-Tenant Isolation & Row-Level Security (RLS)
- **Tenant Sandboxing**: All multi-tenant database tables must enforce Row-Level Security (RLS) or explicit tenancy query scoping (`WHERE tenant_id = current_tenant`).
- **Security Definer Functions**: Ensure database helper functions marked `SECURITY DEFINER` are hardened with explicit search paths (`SET search_path = public`) and prevent recursive escalation loops.
- **RBAC & Authorization**: Verify that manager and collaborator roles only access resources explicitly authorized by owner/membership mappings.

## 2. Authentication & Authorization
- **JWT / Session Token Validation**: All protected API endpoints must strictly validate token signatures, expiration times, and scopes before processing.
- **Secret Management**: Never commit or expose private keys, master database credentials, JWT signing secrets, or third-party API keys in client-side bundles or public repositories. Use `.env` files with `chmod 600`.
- **Role Verification**: Privileged operations (billing, administrative settings, audit logs) must verify user role claims both at gateway/route guards and server-side handlers.

## 3. Rate Limiting & Concurrency Control
- **Rate Limiting**: Public endpoints (login, password reset, OTP dispatch, search queries) must enforce IP/key-based rate limits to mitigate brute-force and DDoS attacks.
- **Race Condition Prevention**: Enforce database-level uniqueness constraints and atomic transactions for state-mutating operations to prevent double-submit or double-spend vulnerabilities.

## 4. File Upload & Input Sanitization
- **Strict MIME & Size Ceilings**: File uploads must validate magic byte headers and allowed MIME types (`image/jpeg`, `image/png`, `application/pdf`) with strict file size limits.
- **Input Sanitization**: Always sanitize and validate user input to eliminate SQL injection, Cross-Site Scripting (XSS), and Remote Code Execution (RCE).
