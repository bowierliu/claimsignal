# Brief: write a synthetic provider-level visit-mix dataset

You are an independent author. You will write a fictional dataset describing how many "visit"
lines each healthcare provider billed at each visit level, plus an answer file. A separate
checking program will later be run over your providers and its output compared with your answers.
You have not seen that program and must not try to guess how it works.

## Rules for you

1. Work only from this brief. Do not read any file outside the output directory named below, do not
   use the network, and do not look at any code, data, test, report or answer belonging to whoever
   gave you this brief.
2. Do not tune the data to what you think a checker would do. Write providers the way real practice
   variation and real over-billing of high visit levels look.
3. Everything is fictional. No real people, providers, plans or codes. Visit codes are fake
   (`X` plus four digits). Do not write real CPT/HCPCS codes or descriptors.
4. When a provider is ambiguous (a reasonable reviewer could go either way), still label it and
   begin its `reason` with `UNSURE:`.
5. Do not edit files after delivering them. If you find a mistake, say so in your reply.

## The idea

Visits are billed at ordered levels, from the lowest (`X0001`) to the highest. In a healthy
specialty, most providers bill the highest level on a modest share of visits, with real
provider-to-provider variation (case mix, patient age, practice style). A provider is an
**intensity outlier** when the share of their visits billed at the highest level is far above
what other providers of the same specialty do, beyond what ordinary variation explains. This is a
reason to review, never proof of anything.

## What to write

Three primary specialties (`S1`, `S2`, `S3`) and one separately declared **contamination
specialty** (`S4`). Each provider belongs to exactly one specialty.

### Each primary specialty (`S1`, `S2`, `S3`)

- At least 45 and at most 70 **ORDINARY** providers: ordinary practice variation, wide but
  plausible. Individual providers' intended highest-level shares should differ substantially (a
  few legitimately sit toward the upper end of the ordinary range). The specialty's typical
  share should differ between the three specialties.
- Between 7 and 9 **TRUE** outliers, with at least 3 labelled `mild` (clearly above the top of the
  ordinary range, but not dramatically) and at least 3 labelled `strong` (far above it).
- Between 7 and 9 **DECOY** providers: they bill the highest level more often than most peers but
  are still inside what is plausible for the specialty (for example a complex-patient practice).
  At least 3 must be labelled `hard`: their share is close to that of a TRUE provider. The rest
  are `easy`.
- TRUE providers must be at most 15% of the specialty's providers; DECOY providers at most 15%.
- Vary volumes: visit lines per provider range from about 10 to about 800, roughly log-spread.
  In each primary specialty include at least 6 providers with 30 or fewer visit lines and at
  least 8 with 31 to 70 visit lines. Low-volume providers can be any label, but each primary
  specialty must have at least 1 low-volume TRUE and at least 1 low-volume DECOY.

### The contamination specialty (`S4`)

A specialty in which over-billing is widespread: at least 30 ORDINARY providers, plus TRUE
outliers making up between 30% and 45% of the specialty's providers (label them `mild` or
`strong`), plus a few DECOY providers. It is a stress case and is analysed separately.

### Generating the counts

Decide each provider's **intended highest-level share** first, then generate its visit counts
with a script and a fixed random seed (counts per visit level for the number of visit lines you
chose). State in your reply that you used a script and the seed. Use at least four visit levels
and put the highest level's count in the last position.

## Files to deliver (put exactly these four files in `/tmp/claimsignal_intensity_v2_author/`)

### 1. `rules.json`

```json
{"visit_codes": ["X0001", "X0002", "X0003", "X0004", "X0005"]}
```

Ordered from lowest to highest visit level; at least four codes, all `X` plus four digits.

### 2. `providers.jsonl`: one provider per line

```json
{"provider_id": "PRV-0417", "specialty": "S1", "visit_counts": {"X0001": 4, "X0002": 21, "X0003": 30, "X0004": 12, "X0005": 9}}
```

`visit_counts` has one non-negative integer for every code in `rules.json`. Provider ids are unique
and must not encode the label, specialty order or volume. Shuffle the lines so file order carries no
information.

### 3. `labels.jsonl`: the answer file (kept separate; it is sealed before anyone scores)

One line per provider, same ids:

```json
{"provider_id": "PRV-0417", "specialty": "S1", "stratum": "primary", "label": "TRUE", "severity": "mild", "decoy_kind": null, "intended_high_share": 0.46, "reason": "One sentence."}
```

- `stratum`: `primary` for S1 to S3, `contamination` for S4.
- `label`: `TRUE`, `DECOY` or `ORDINARY`.
- `severity`: `mild` or `strong` for TRUE; `null` otherwise.
- `decoy_kind`: `hard` or `easy` for DECOY; `null` otherwise.
- `intended_high_share`: your plan for the provider's highest-level share (0 to 1), decided before
  you generated counts.
- `reason`: one sentence; start with `UNSURE:` when ambiguous.

### 4. `AUTHOR_NOTE.md`

Short: how you generated the data (script, seed, distributions per specialty), and answers to these
checks: (a) providers per specialty and label; (b) TRUE and DECOY share of each primary specialty;
(c) counts of low-volume providers per primary specialty; (d) that every id is unique and every
label row matches a provider; (e) that no real codes or identifiers appear; (f) how many
providers you marked `UNSURE:`.
