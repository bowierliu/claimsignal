---
name: decision-logging
description: Record a project decision (options, choice, why) in DECISIONS.md and the facts in SESSION_LOG.md. Use whenever a choice is made or the owner answers a decision gate.
---

# Decision logging

At every open decision gate: present 2-3 options with a recommendation, wait for the owner, then
log the outcome.

## `DECISIONS.md` (reasons)

Newest last. Add under a dated heading (`## YYYY-MM-DD: <topic>`). Use a table when there are
several small decisions, or short bullets for one. Each decision records:

- **Options** considered (including the one rejected and why),
- **Choice**, and who made it (owner-approved vs agent default),
- **Why**, including the trade-off accepted.

Conservative defaults chosen by the agent are labelled as such so the owner can revisit them.

## `SESSION_LOG.md` (facts)

Facts only, newest last: what was run, what was observed, measured numbers, spend, commit hashes.
No opinions or reasons here. Never write a number you did not measure in this session; count
things with a command instead of estimating.

## Also

- Prompt changes: include the eval comparison against the previous prompt version.
- Failures belong in `KNOWN_FAILURES.md`, not in a decision entry.
- Keep entries free of secrets and employer-specific content.
