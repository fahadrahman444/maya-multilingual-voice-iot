---
name: anti-slop-cleanup
description: Enforces the Ponytail Minimalist Ladder and eliminates CodeSlop (residual dead code, loose any, padding comments, fake try-catches, and bloated dependencies) across any codebase.
---

# Anti-Slop & Minimalist Engineering Protocol

Use this skill when generating new code, refactoring existing files, or auditing pull requests across any codebase.

## 1. The Ponytail Minimalist Ladder
Before writing any new lines of code, evaluate each rung in order and stop at the first that resolves the requirement:
1. **YAGNI (You Aren't Gonna Need It):** Does this feature or abstraction strictly need to exist? If speculative, eliminate it.
2. **Codebase Reuse:** Search for and reuse existing helpers, utility functions, components, and hooks in the project.
3. **Standard Library:** Can the standard library of the language (Go, TypeScript/JS, Python, Rust) do this without extra libraries?
4. **Native Platform Features:** Use native HTML/CSS/browser capabilities (e.g. `<input type="date">`, native dialogs, native scroll) instead of heavy JS packages.
5. **Existing Installed Dependency:** If standard library is insufficient, check already-installed dependencies. Never install a package for trivial utility functions.
6. **One-Line Solution:** Can this be implemented cleanly in a single line or short expression?
7. **Minimal Code:** Only after exhausting 1–6, write the smallest contiguous block of clear, readable code.

## 2. Slop Patterns to Never Introduce (and Always Clean)
| Pattern | Rule |
|---|---|
| **Padding Comments** | Remove obvious comments like `// fetch data` over `fetchData()`. Write self-documenting code. |
| **Useless Try/Catch** | Do not catch an error merely to log and re-throw without recovery. |
| **Commented-Out Code** | Never commit commented-out dead code blocks. Rely on Git history. |
| **Loose `any` Types** | Never use `: any`. Define clean interfaces or use `unknown` with type guards. |
| **Redundant `async/await`** | Do not mark functions `async` if they do not contain `await`. Do not use `return await x;` outside try/catch. |
| **Trivial Arrow Wrappers** | Prefer `(items) => items.map(formatName)` over `items.map((x) => formatName(x))`. |
| **Future-Proof Manager Bloat** | Avoid single-method `*Manager`, `*Helper`, `*Provider` class abstractions. Keep functions pure and concise. |

## 3. Four-Phase Cleanup Workflow
1. **Analyze:** Inspect the file and imports. Identify unnecessary client tags, inline styles, dead variables, and loose types.
2. **Refactor:** Apply minimalist refactoring using platform standards and strict typing.
3. **Verify:** Check compilation (`tsc --noEmit`, `go test`, `cargo check`, or stack linter).
4. **Clean Slop:** Run linters/fixers to eliminate unambiguous structural bloat.
