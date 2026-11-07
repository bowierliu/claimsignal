# Brief: write a blind test set of synthetic claims with line-level answers

You are an independent author. You will write synthetic health-plan claims that contain known
billing anomalies **on specific claim lines**, near-miss look-alikes, and ordinary claims, plus an
answer file that names the exact lines. Someone else will run a checking program over your claims and
compare the lines it points to with your answers. You have not seen that program and must not try to
guess how it works.

## Rules for you

1. Work only from this brief. Do not read any file outside the output directory named below, do not
   use the network, and do not look at any code, data, test, report or answer belonging to whoever
   gave you this brief.
2. Do not tune cases to what you think a checker would do. Write cases the way the public rules
   describe the problem, and state your own rules in `rules.json`.
3. Everything is fictional. No real people, providers, plans or claims. Procedure codes are fake
   (`X` plus four digits). Do not write real CPT/HCPCS codes or descriptors.
4. When a case is ambiguous (a reasonable reviewer could go either way), still label it, and begin
   its `reason` with `UNSURE:`.
5. Do not edit files after delivering them. If you find a mistake, say so in your reply.

## The three line-level anomaly types

| type | plain-English definition | which line(s) belong in `line_refs` |
|---|---|---|
| `unbundling` | A component service is billed next to the comprehensive service that already includes it, for the same member, provider and service date, without the modifier that allows separate payment. | The **component** line(s) that should not be paid separately (not the comprehensive line). |
| `excess_units` | A line reports more units than the maximum your rules allow for that code on one line. | Each line whose own units exceed its code's limit. |
| `date_anomaly` | A line is dated outside the claim's own service period (before `service_from` or after `service_to`). | Each line dated outside the claim period. |

Do **not** write duplicate-claim cases or provider-level cases of any kind. Every claim you write
belongs to exactly one case or is an ordinary clean claim.

## Files to deliver (exactly these three, in `/tmp/claimsignal_lines_author/`)

### 1. `claims.jsonl`: one claim per line, JSON

Each line is one claim with member, provider, lines and diagnoses written in full (repeat member and
provider details on every claim that uses them and keep them identical):

```json
{
  "claim_id": "CLM0001",
  "member": {"member_id": "MEM001", "age_band": "40-49", "sex": "F", "plan_type": "PPO", "region": "R1"},
  "provider": {"provider_id": "PRV001", "specialty": "S1", "region": "R1", "group_id": "G1"},
  "service_from": "2026-11-03",
  "service_to": "2026-11-03",
  "place_of_service": "PS1",
  "total_billed": "245.00",
  "diagnoses": ["J02.9"],
  "lines": [
    {"line_no": 1, "code": "X0101", "units": 1, "billed_amount": "245.00",
     "service_date": "2026-11-03", "modifiers": [], "dx_pointer": 1}
  ]
}
```

| item | rule |
|---|---|
| member | `member_id`, `age_band`, `sex`, `plan_type`, `region`. Coarse attributes only |
| provider | `provider_id`, `specialty`, `region`, `group_id`. One id per provider |
| claim | `claim_id` (unique), `service_from`, `service_to`, `place_of_service`, `total_billed`; `diagnoses` is an ordered, non-empty list |
| line | `line_no` (1, 2, ...), `code`, `units` (integer, at least 1), `billed_amount`, `service_date`, `modifiers` (ordered list), `dx_pointer` (1-based index into the claim's diagnoses) |
| formats | Dates are ISO `YYYY-MM-DD`; every date (including out-of-period line dates) must fall between 2026-10-01 and 2027-09-30. Money is a decimal string with two places. `total_billed` equals the sum of the line `billed_amount` values. `place_of_service` is one of `PS1`, `PS2`, `PS3` |
| modifiers | Synthetic: `M1`, `M2`, `M3`. Which modifier (if any) allows a bundled pair to be paid separately is stated per pair in `rules.json` |
| diagnoses | Use only these valid ICD-10-CM codes (codes only, no descriptions): `J02.9`, `I10`, `E11.9`, `F41.9`, `J06.9`, `R51.9`, `K21.9`, `N39.0`, `E78.5`, `J45.909`, `L30.9`, `H10.9`, `G43.909`, `M54.50`, `R10.9`, `Z00.00`, `B34.9`, `Z23`, `E03.9`, `F32.9` |

Every claim has **at least two lines**, and most have three or four. Where a claim spans several
days, line dates vary within the claim period.

### 2. `rules.json`: the rules of your invented world

```json
{
  "procedure_codes": ["X0101", "X0102"],
  "visit_codes": ["X0001", "X0002", "X0003"],
  "bundle_pairs": [
    {"comprehensive_code": "X0201", "component_code": "X0202", "exception_modifier": "M1"}
  ],
  "unit_limits": [
    {"code": "X0301", "max_units": 4}
  ]
}
```

`procedure_codes` lists every non-visit code you use; `visit_codes` lists at least three visit codes
(lowest to highest level). Every code on every line must appear in one of those two lists. Define at
least eight bundle pairs and at least eight unit limits (different codes, different limits). Make
sure no clean claim, decoy or anomaly accidentally breaks your own rules in a way you did not intend.

### 3. `labels.jsonl`: the answer file (separate; never put answers in `claims.jsonl`)

One line per case:

```json
{"case_id": "L001", "type": "excess_units", "label": "TRUE", "claim_ids": ["CLM0012"], "provider_id": null, "reason": "One sentence.", "case_kind": "multi_line", "line_refs": [{"claim_id": "CLM0012", "line_no": 2}], "tempting_line_refs": [{"claim_id": "CLM0012", "line_no": 3}]}
```

- `type`: one of `unbundling`, `excess_units`, `date_anomaly`, or `clean` for an ordinary claim.
- `label`: `TRUE` (anomaly present), `DECOY` (looks similar but is fine), or `CLEAN` (ordinary claim,
  `type` = `clean`).
- `claim_ids`: every claim in the case (one claim per case in this task). `provider_id` is `null`.
- `reason`: one sentence; start with `UNSURE:` when ambiguous.
- `case_kind` (one of): `standard`, `multi_line`, `near_miss`, `tempting_clean`.
- `line_refs`: for a `TRUE` case, **every** line that is itself the anomaly, per the table above
  (`claim_id` and `line_no`). Must be a non-empty list for TRUE and an empty list for DECOY and CLEAN.
- `tempting_line_refs`: lines that look like the anomaly at a glance but are not (empty list when
  none). Mainly used in `near_miss` and `tempting_clean` cases, and in TRUE cases that also contain a
  look-alike line.
- Every claim in `claims.jsonl` belongs to exactly one case (clean claims get a `CLEAN` case row).

## The task

For each of the three types write:

- **12 TRUE cases.** Include at least 6 `multi_line` cases (a claim with three or more lines where
  only some lines are the anomaly), at least 3 cases where **two different lines** of the same claim
  are the anomaly, at least 3 multi-day claims, and varied codes, units and modifier patterns.
- **8 DECOY cases of kind `near_miss`:** multi-line claims that differ from a TRUE case in exactly
  one detail (for example a line exactly at its limit, a line dated on the last day of the period, a
  component paired with the exception modifier, a component billed on a different date from its
  comprehensive code, a modifier on the wrong line). Put the look-alike line(s) in
  `tempting_line_refs`.
- **6 DECOY cases of kind `tempting_clean`:** claims with a line that looks suspicious at a glance but
  is plainly fine under your rules (for example a very large unit count on a code whose limit is
  high, the same code on two lines that each stay within the limit, a component code with no
  comprehensive code on the claim, a line dated inside a long multi-day period). Put the tempting
  line(s) in `tempting_line_refs`.

Also write **30 CLEAN** claims (two to four lines each; varied codes; one-day and multi-day) that
contain none of the anomalies and break none of your rules.

That is 3 x (12 + 8 + 6) = 78 case claims plus 30 clean claims.

Because this is large, write a small script (standard library only, fixed random seed) to generate
the claims, but decide each case's anomaly and its `line_refs` yourself in the script before
generating so the answers are exact. State in your reply that you used a script and the seed.

## Before you reply

Check yourself and report: (a) number of claims; (b) cases per type, label and `case_kind`; (c) that
every claim id is unique; (d) that every code is in `rules.json`; (e) that `total_billed` matches
the lines; (f) that every `line_refs` entry points to a real line and that each TRUE case's lines
really violate your stated rule and no other line in the claim does; (g) that no real code
descriptors, names or identifiers appear; (h) how many cases you marked `UNSURE:`.
