---
name: context-and-session-optimization
description: Guidelines and tools for reducing token consumption, preventing context amnesia, avoiding feedback death loops, and maintaining persistent state across long sessions.
---

# Universal Context & Session Optimization Skill

Use this skill to optimize LLM context utilization, prevent context rot, and maintain fast, precise agent performance across any project.

## 1. Task-Aware Context Management
- **Targeted Reading:** Only read the exact files or functions needed for the task. Avoid reading broad trees of unneeded directories.
- **Graduated Inspection:** Start with symbols and interfaces (`map`/`signatures`), inspect relevant code bodies (`context`), and read callers/callees only when debugging deep bugs (`deep`).
- **Signature-First Planning:** When proposing architectures or refactors, specify file signatures and API contracts rather than generating complete speculative code.

## 2. Preventing the Feedback Death Loop
- **The Loop:** `Write Code → Compile Error → Guess Fix → Break Adjacent Module → Compound Context`.
- **The Solution:**
  1. If a test or type check fails, stop and understand the exact compiler error.
  2. Inspect the contract/types involved rather than blindly appending code.
  3. One fix per step, verified immediately.

## 3. Managing Context Compaction & Memory
- **Persistent State File (`.agents/state/STATE.md`):** Write long-term decisions, selected architectures, and constraints to `STATE.md`.
- **Session Discipline:**
  - One major feature or task per conversation session.
  - If beginning a completely unrelated feature, start a fresh session to prevent context degradation ("context rot").
- **Survivability Across Compaction:**
  - Project rules in root `AGENTS.md` and memory files in `.agents/state/` survive compaction.
  - Ephemeral tool outputs get summarized away—crucial discoveries should be written to markdown files on disk.
