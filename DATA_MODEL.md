# Data model

Status: **not designed yet** (Phase 2). This file records the constraints the model must meet.
Entities and fields will be added here, with decisions in `DECISIONS.md`.

## Scope (from the brief)

Synthetic payer data: members, providers, claims, claim lines, and flags, with seeded anomalies
that have known ground truth so tools and the agent can be scored.

## Constraints

- Everything is synthetic. No real member, provider, or claim data, and no employer-specific
  schemas, fields, or rules.
- Procedure codes are obviously fake (`X0001` style). CPT descriptors never appear.
- Each seeded anomaly has a recorded label (type, affected lines, why), generated with a fixed
  seed so datasets are reproducible.
- Field names and shapes follow public concepts only, with any claim about a public standard
  tied to a manifest source.
- Persistence is an open gate (Phase 2): options and a recommendation will be presented first.
