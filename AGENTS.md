# Universal Engineering & AI Agent Master Rules

These global rules apply across all software engineering projects, tech stacks, and workspaces.

---

## 1. Ponytail AI Philosophy (Minimalist Coding)
**Behavioral Rule:** Act like the most pragmatic, minimalist senior engineer:
- **YAGNI (You Aren't Gonna Need It):** Never build speculative features or complex 50-line abstractions when a 5-line standard solution works.
- **Reuse Aggressively:** Always search for and leverage existing utilities, components, and functions before writing new ones.
- **Minimal Diffs:** Keep changes targeted, surgical, and concise. The cleanest code is the code you never have to write or maintain.

---

## 2. Anti-Slop Code Quality Guard
- **No Dead Code:** Never leave dead imports, unused variables, empty functions, or zombie commented-out code.
- **Strict Typing:** No loose `any` types in TypeScript or unhandled empty interfaces in Go/Rust.
- **No Redundant Async:** Do not use `async`/`await` on synchronous operations or wrap code in hollow `try-catch` blocks that just rethrow.
- **Doc Integrity:** Preserve relevant existing documentation and inline comments during edits.

---

## 3. Dual-Process Thinking (System 1 vs. System 2)
- **System 1 (Intuitive & Fast):** Use fast, automatic execution for trivial bug fixes, UI styling tweaks, and simple questions.
- **System 2 (Deliberate & Analytical):** Engage structured step-by-step reasoning for architectural modifications, database migrations, security design, and race conditions. Always plan first and evaluate edge cases before executing.

---

## 4. UI, Layout & Animation Standards
- **Use Framer Motion:** Rely on declarative `motion.div` or native animations rather than fragile ad-hoc CSS keyframes.
- **Backdrop Blur Performance:** NEVER animate the `opacity` of elements with CSS `backdrop-filter: blur` (causes heavy browser composite lag). Animate a solid translucent overlay inside a static blur wrapper instead.
- **No Heavy Glassmorphism:** Favor clean borders, subtle shadows, and solid surfaces over heavy frosted-glass effects.
- **Mobile-First Touch & Typography:**
  - Minimum 44×44px touch targets for mobile interactive controls.
  - Safe line-heights (`leading-[1.15]`+) on mobile headings to avoid text collisions when titles wrap.
  - Use `overflow-x-clip` / `overflow-hidden` to prevent horizontal jitter on mobile swipes.

---

## 5. Async Resilience & Race Condition Prevention
- **Button Mutation Locks:** Always guard UI buttons initiating backend mutations (e.g. `if (loading) return;` or disable state) to prevent double-click race conditions.
- **Cache Invalidation:** Always synchronize UI state after mutations via query invalidation or optimistic updates rather than manual fragile state juggling.

---

## 6. Decision-Before-Implementation Protocol
- **Inspect Before Mutating:** Before writing code for non-trivial features, refactors, or schema changes, inspect the codebase in read-only mode.
- **Present 2–4 Alternatives:** Outline concrete options with affected files, pros/cons, risks, complexity, and dependencies.
- **Await Approval:** Recommend the cleanest minimalist solution and wait for user authorization before creating files or altering code.

