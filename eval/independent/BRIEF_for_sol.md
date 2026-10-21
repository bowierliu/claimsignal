# Brief: write a small, blind test set of synthetic health-plan claims

You are an independent author. You will write synthetic claims that contain known billing
anomalies, near-miss look-alikes, and ordinary claims, plus an answer file. Someone else will run a
checking program over your claims and compare its output with your answers. You have not seen that
program and must not try to.

## Rules for you

1. Do not look at any code, database, test, evaluation file or answer key belonging to the person
   who gave you this brief. Work only from this brief and the public sources below.
2. Do not tune cases to what you think a checker would do. Write cases the way the public rules
   describe the problem.
3. Everything is fictional. No real people, providers, plans or claims. Procedure codes are fake
   (`X0001` style: the letter X and four digits). Do not write or paraphrase real CPT/HCPCS code
   descriptors anywhere.
4. When a case is ambiguous (a reasonable reviewer could go either way), still label it, and
   begin its reason with `UNSURE:`. Do not guess silently.
5. Do not edit files after delivering them. If you find a mistake, say so in your reply instead.

## Public sources you may use

| id | URL |
|---|---|
| ncci-pm-intro | https://www.cms.gov/files/document/0-introduction-ncci-medicare-policy-manual-2026-final.pdf |
| ncci-pm-ch01 | https://www.cms.gov/files/document/01-chapter1-ncci-medicare-policy-manual-2026-final.pdf |
| ncci-pm-ch11 | https://www.cms.gov/files/document/11-chapter11a-ncci-medicare-policy-manual-2026-final.pdf |
| clm104-ch01 | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c01.pdf |
| clm104-ch12 | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c12.pdf |
| clm104-ch26 | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c26.pdf |
| pim-ch02 | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/pim83c02.pdf |
| oig-mod59 | https://oig.hhs.gov/documents/evaluation/2330/OEI-03-02-00771-Complete%20Report.pdf |
| oig-mod25 | https://www.oig.hhs.gov/oei/reports/oei-07-03-00470.pdf |
| oig-va-dup | https://oig.hhs.gov/documents/audit/9651/A-09-22-03004-Complete%20Report.pdf |
| oig-jh-mue | https://oig.hhs.gov/oas/reports/region6/61300010.pdf |
| oig-podiatry-em | https://www.oig.hhs.gov/documents/root/11292/A-09-22-03012.pdf |
| oig-eye-em | https://www.oig.hhs.gov/documents/audit/10286/A-09-23-03014.pdf |
| icd10cm-fy27-guidelines | https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/ICD-10-CM-October-1-2026-FY27-Guidelines.pdf |
| icd10cm-fy27-code-descriptions | https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip |

These describe the real-world ideas (paired-code edits and modifiers, units per service, duplicate
billing, visit-level coding patterns). The test world is smaller and invented: you will state its
rules yourself in `rules.json` (below).

## The five anomaly types

| type | plain-English definition |
|---|---|
| `duplicate_claim` | The same services for the same member from the same provider are billed more than once for the same service date or period. |
| `unbundling` | A component service is billed separately next to the comprehensive service that already includes it, on the same date for the same member and provider, without a modifier that allows separate payment. |
| `excess_units` | A service line reports more units than the maximum your rules allow for that code on one line. |
| `intensity_outlier` | A provider bills the highest-level visit code far more often than other providers of the same specialty do. |
| `date_anomaly` | A service line is dated outside the claim's own service period. |

## Files to deliver (three)

### 1. `claims.jsonl`: one claim per line, JSON

Each line is one claim with its member, provider, lines and diagnoses written in full (repeat
the member and provider details on every claim that uses them, and keep them identical):

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

Field rules (public claim concepts only):

| item | rule |
|---|---|
| member | `member_id`, `age_band`, `sex`, `plan_type`, `region`. Coarse attributes only; no names, no dates of birth, no addresses |
| provider | `provider_id`, `specialty`, `region`, `group_id`. One id per provider (no separate billing and rendering provider) |
| claim | `claim_id` (unique), `service_from`, `service_to`, `place_of_service`, `total_billed`; `diagnoses` is an ordered list |
| line | `line_no` (1, 2, ...), `code`, `units` (integer), `billed_amount`, `service_date`, `modifiers` (ordered list), `dx_pointer` (1-based index into the claim's diagnoses) |
| formats | Dates are ISO `YYYY-MM-DD`. Money is a decimal string with two places. `total_billed` equals the sum of the line `billed_amount` values. `place_of_service` is one of `PS1`, `PS2`, `PS3` |
| modifiers | Synthetic: `M1`, `M2`, `M3`. Which modifier (if any) allows a bundled pair to be paid separately is stated per pair in `rules.json` |
| diagnoses | Real ICD-10-CM FY2027 codes taken from the public code list above (codes only, no descriptions). All service dates must fall between 2026-10-01 and 2027-09-30, the FY2027 window, including the dates of any "outside the claim period" lines |

### 2. `rules.json`: the rules of your invented world

Invent small, internally consistent rules for your world, in the spirit of the public sources.
You decide them; keep them plausible and write them down:

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

`procedure_codes` lists every non-visit code you use. `visit_codes` lists the visit codes ordered from
the lowest level to the highest level (at least three). Every code on any claim line must appear in
one of those two lists. Use obviously fake codes only (`X` plus four digits). Define at least five
bundle pairs and at least five unit limits. Make sure no clean claim, decoy, or anomaly accidentally
breaks your own rules in a way you did not intend.

### 3. `labels.jsonl`: the answer file (kept separate; never put answers in `claims.jsonl`)

One line per case:

```json
{"case_id": "C001", "type": "unbundling", "label": "TRUE", "claim_ids": ["CLM0012"], "provider_id": null, "reason": "One sentence on why this is, or is not, the anomaly."}
```

- `type` is one of the five type names, or `clean` for an ordinary claim.
- `label` is `TRUE` (the anomaly is present), `DECOY` (looks similar but is fine) or `CLEAN`
  (ordinary claim; use `type` = `clean`).
- `claim_ids` lists every claim in the case (a duplicate pair has two). For `intensity_outlier`
  cases the case is the provider: put the provider's id in `provider_id` and leave `claim_ids` as
  an empty list.
- `reason` is one sentence. Start it with `UNSURE:` when the case is ambiguous.
- Every claim in `claims.jsonl` belongs to exactly one case, except claims of the ordinary
  background providers in the intensity block (see below), which need no case line.

## The task

For each of the four claim-level types (`duplicate_claim`, `unbundling`, `excess_units`,
`date_anomaly`) write:

- **10 TRUE cases.** Vary how the anomaly shows up (different codes, different numbers of lines,
  different modifier patterns, different dates, one-line and multi-line claims, multi-day
  claims). Do not write ten copies of the same shape.
- **10 DECOY cases:** near misses that should NOT be flagged. At least 3 of the 10 must be hard:
  they differ from a TRUE case in exactly one detail.
- Each claim belongs to one case only. Keep each case's member and provider separate from other
  cases where you can, so that cases do not interfere with each other.

Also write **40 CLEAN claims**: ordinary, plausible claims (varied codes, one to four lines, a
mix of one-day and multi-day claims) that contain none of the five anomalies and break none of
your rules.

That gives 100 claim-level case claims (a duplicate case uses two claims) plus 40 clean claims.

### The provider-level block (`intensity_outlier`)

This type needs many claims per provider, so it is a separate block that is not part of the 140.
Use one single specialty for the whole block. Write:

- **10 TRUE outlier providers** and **10 DECOY providers**. A DECOY provider bills the top visit
  level more often than most peers but is still inside what is normal for the specialty. At
  least 3 of the 10 decoys must be hard (close to a TRUE provider in their share).
- **At least 25 ordinary background providers** in the same specialty, billing a normal mix.
- Give every one of these providers at least 50 visit-code lines (visit codes from your
  `visit_codes` list), spread over many members and dates, so a share of the top visit level can
  be computed fairly. One visit line per claim is fine.
- Providers in this block must not appear in any claim-level case or clean claim, and vice
  versa.

Because this block is large, write a small script to generate it (and, if you like, the other
claims too), with a fixed random seed. Make sure the script's output obeys every rule above and
that you decide each provider's intended share yourself before generating. You do not need to
deliver the script, but you must state in your reply that you used one.

## Before you reply

Check yourself and report: (a) number of claims, (b) number of cases per type and label, (c) that
every claim id is unique, (d) that every code is in `rules.json`, (e) that `total_billed` matches
the lines, (f) that no real code descriptors, names or identifiers appear, (g) how many cases you
marked `UNSURE:`, (h) whether you used a script.

Deliver `claims.jsonl`, `rules.json` and `labels.jsonl`, each as a downloadable file or a single
code block.
