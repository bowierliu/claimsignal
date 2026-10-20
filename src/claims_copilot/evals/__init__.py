"""Phase 7 evaluation system: case schema, deterministic split, metric definitions.

Nothing in this package calls a provider or opens the truth store. The pre-registered thresholds
live in `eval/phase7_preregistration.json` and are loaded, not copied, so the code and the
committed document cannot drift apart.
"""
