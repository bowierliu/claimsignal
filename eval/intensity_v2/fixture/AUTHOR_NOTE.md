# AUTHOR_NOTE

## How the data was generated

A standard-library Python script (run once, inline, not saved) with `random.Random(seed)`, seed **20261107**.
For each provider: (1) choose a label and an intended highest-level share; (2) choose a visit-line count; (3) draw the highest-level
count as Binomial(n, share); (4) spread the remaining lines over the lower four levels with a specialty-specific base mix
tilted per provider by lognormal noise. The highest level (`X0005`) is last.

Volumes are log-uniform on 10-800, then adjusted so each primary specialty has >=6 providers with <=30 lines and >=8 with
31-70 lines, plus a low-volume TRUE and a low-volume DECOY.

Intended-share distributions (ORDINARY = clipped Beta; the first few ORDINARY providers per specialty were set to the upper end of the range):

| Spec | ORDINARY | upper-end ORDINARY | mild TRUE | strong TRUE | hard DECOY | easy DECOY |
|---|---|---|---|---|---|---|
| S1 | Beta(3,13.5) clip 0.04-0.34 (mean ~0.18) | 0.28-0.34 | 0.47-0.55 | 0.66-0.85 | 0.40-0.44 | 0.33-0.38 |
| S2 | Beta(5,11.5) clip 0.10-0.48 (mean ~0.30) | 0.42-0.48 | 0.60-0.68 | 0.80-0.93 | 0.52-0.56 | 0.47-0.52 |
| S3 | Beta(1.8,16) clip 0.02-0.20 (mean ~0.10) | 0.17-0.21 | 0.28-0.36 | 0.50-0.72 | 0.24-0.27 | 0.215-0.235 |
| S4 (contamination) | Beta(4,12) clip 0.08-0.35 | 0.30-0.35 | 0.48-0.60 | 0.70-0.92 | 0.40-0.45 | 0.36-0.40 |

Primary specialties: 8 TRUE (4 mild, 4 strong) and 8 DECOY (4 hard, 4 easy) each. S4: 20 TRUE (10 mild, 10 strong), 4 DECOY.

Caveats: some easy DECOY ranges overlap the upper-end ORDINARY ranges by design; these overlaps are real ambiguity and are
partly flagged `UNSURE:`. Mild TRUE and hard DECOY ranges are deliberately close (gap of about 0.03-0.07 in share).

## Checks

**(a) Providers per specialty and label**

| Specialty | ORDINARY | TRUE (mild/strong) | DECOY (hard/easy) | Total |
|---|---|---|---|---|
| S1 | 55 | 8 (4/4) | 8 (4/4) | 71 |
| S2 | 62 | 8 (4/4) | 8 (4/4) | 78 |
| S3 | 50 | 8 (4/4) | 8 (4/4) | 66 |
| S4 | 34 | 20 (10/10) | 4 (2/2) | 58 |

**(b) TRUE and DECOY share of each specialty**

- S1: TRUE 8/71 = 11.3%, DECOY 8/71 = 11.3%
- S2: TRUE 8/78 = 10.3%, DECOY 8/78 = 10.3%
- S3: TRUE 8/66 = 12.1%, DECOY 8/66 = 12.1%
- S4: TRUE 20/58 = 34.5%, DECOY 4/58 = 6.9% (S4 TRUE must be 30-45%)

**(c) Low-volume providers per primary specialty (visit lines)**

- S1: <=30 lines: 23 (TRUE 4, DECOY 1); 31-70 lines: 15; min 11, max 683
- S2: <=30 lines: 24 (TRUE 4, DECOY 4); 31-70 lines: 16; min 10, max 702
- S3: <=30 lines: 17 (TRUE 4, DECOY 1); 31-70 lines: 11; min 11, max 709

**(d)** 273 providers, 273 unique ids; 273 label rows, label ids == provider ids: True. Ids are random draws of 4 digits (no relation to label, specialty or volume); both files shuffled separately.

**(e)** All codes are X0001-X0005; no real CPT/HCPCS codes, descriptors, people, providers or plans appear. Provider ids are random `PRV-####`.

**(f)** 30 providers marked `UNSURE:` (by specialty: S1 7, S2 9, S3 9, S4 5). Rule: all hard decoys, low-volume (<=30 lines) mild TRUE, and upper-end ORDINARY providers with <=70 lines.

## Realized highest-level shares (counts, not plans)

| Spec | ORD min/median/max (intended) | mild TRUE range | strong TRUE range | hard DECOY range | easy DECOY range |
|---|---|---|---|---|---|
| S1 | 0.06/0.17/0.34 | 0.50-0.51 | 0.71-0.85 | 0.41-0.43 | 0.35-0.38 |
| S2 | 0.13/0.29/0.48 | 0.60-0.66 | 0.82-0.92 | 0.52-0.55 | 0.47-0.52 |
| S3 | 0.02/0.11/0.20 | 0.30-0.34 | 0.53-0.70 | 0.24-0.27 | 0.22-0.23 |
| S4 | 0.08/0.26/0.35 | 0.49-0.60 | 0.72-0.91 | 0.42-0.43 | 0.36-0.39 |

Realized shares (from counts) differ from intended for low-volume providers by binomial noise; intended shares are in `labels.jsonl`.
