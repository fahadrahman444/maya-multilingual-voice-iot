---
name: decision-before-implementation
description: Universal Decision-Before-Implementation Protocol. Guides inspecting code in read-only mode, formulating 2–4 distinct alternatives with trade-offs, and waiting for explicit user approval before writing any code.
---

# Universal Decision-Before-Implementation Protocol

Use this skill whenever receiving a request for a new feature, UI redesign, architectural refactor, database schema change, dependency addition, or non-trivial performance optimization across any software project.

## Core Mandate
```
DISCUSS → INSPECT (Read-Only) → PRESENT 2–4 OPTIONS → RECOMMEND → WAIT FOR APPROVAL → IMPLEMENT → VERIFY
```

> [!IMPORTANT]
> **Do not write or modify implementation code, create files, install dependencies, run migrations, or execute mutating commands during the decision phase.** Codebase inspection and read-only analysis are strictly required first.

---

## 1. Step-by-Step Decision Flow

### Step 1: Understand Objective & Scope
- Identify the user's core intent (business value, UX outcome, bug fix, scalability, or performance improvement).
- Identify the impacted boundaries: frontend, backend APIs, background workers, database schema, CI/CD, or infrastructure.

### Step 2: Read-Only Inspection
- Use read-only inspection tools (`view_file`, `git grep`, search) to inspect relevant components, contracts, APIs, or database schemas.
- Identify existing reusable utilities and standard library solutions (The Ponytail Minimalist Ladder).
- Determine the smallest reasonable change that could achieve the objective cleanly without over-engineering.

### Step 3: Formulate 2–4 Genuine Alternatives
Present distinct, realistic approaches. Do not offer trivial non-options. For each option, clearly specify:
1. **Application Changes:** What specifically changes in behavior, data flow, or UI.
2. **Affected Areas:** Files, components, APIs, endpoints, or database tables impacted.
3. **Trade-offs:** Benefits (pros) vs. disadvantages (cons).
4. **Complexity & Risk:** Implementation complexity and potential risks to existing functionality or performance.
5. **Dependencies & Migrations:** Explicitly state if new dependencies, third-party packages, or database migrations are required.

### Step 4: Recommend & Halt
- State your clear recommendation and provide the specific engineering rationale.
- **Stop calling mutating tools and wait for the user's explicit choice.** Never treat a recommendation, silence, or the original prompt as approval.

### Step 5: Implement Approved Scope Only
- Implement strictly the option selected by the user.
- If an unexpected technical obstacle arises requiring expanding the scope or changing the approach, stop and ask again.

### Step 6: Verify & Report
- Review git diffs, run `gemini-kit verify`, test suites, or typechecks.
- Report all modified files and their exact purpose to the user.

---

## 2. Decision Presentation Template

Use this standard structure when presenting options to the user:

```markdown
### Analysis & Context
[Brief 1-2 sentence summary of current architecture and objective]

---

### Option 1: [Approach Name] (Recommended)
- **What changes:** [Concrete description of behavior or architecture]
- **Affected areas:** [Key files, modules, endpoints, or schemas]
- **Pros:** [Benefits, simplicity, performance]
- **Cons & Risks:** [Limitations, risks, edge cases]
- **Complexity:** [Low / Medium / High]
- **Dependencies / Migrations:** [None / List additions]

---

### Option 2: [Alternative Approach Name]
- **What changes:** [Concrete description]
- **Affected areas:** [Key files, modules, endpoints]
- **Pros:** [Benefits]
- **Cons & Risks:** [Limitations, risks]
- **Complexity:** [Low / Medium / High]
- **Dependencies / Migrations:** [None / List additions]

---

### Recommendation & Rationale
[Explain why Option 1 is recommended based on minimalism, safety, and maintainability]
```

---

## 3. Scope Expansion Guardrails

- **Zero Speculative Code:** Never preemptively write "Option 1" in code before the user selects it.
- **Unambiguous Approval:** Accept responses such as `"Option 1"`, `"Option 2 with adjustments"`, `"Combine 1 and 2"`, or `"Show another way"`.
- **Pivot Protocol:** If the user rejects the options or suggests a different direction, return immediately to the read-only inspection and decision phase.
