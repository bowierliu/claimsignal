---
name: teach
description: Explain a concept simply, anchored in this codebase. Run as /teach <concept>. Never modifies code.
disable-model-invocation: true
---

# /teach <concept>

Explain `<concept>` to the owner. Read-only: do NOT edit, create, or delete any file and do not
run commands that change state. Use `file-scout` or read tools to find where the concept appears.
If the owner's level is unclear, ask first (one question).

## Format (default under 300 words)

1. **One sentence**, plain language.
2. **Everyday analogy.**
3. **Where it shows up in THIS codebase**: real file references with line ranges you have read, or
   say it does not appear yet.
4. **Tiny example** (a few lines, not copied from memory if it claims to be from the repo).
5. **One common misconception.**
6. **One question** to check understanding. Wait for the answer.

Do not cite sources from memory; if a fact needs a source, say so and point to the manifest or
offer to fetch it.
