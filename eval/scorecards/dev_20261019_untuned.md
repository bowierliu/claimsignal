# Tool scorecard: dev seed 20261019, untuned (params d6536f635e00)

payer sha256 2e78ddbcf0c47626...  claims scored 40060  params d6536f635e00  full ICD list used: True

| Parameter | Value |
|---|---|
| ruleset | synthetic-v1 (invented rules, not NCCI or MUE) |
| z_threshold | 3.5 |
| min_visit_lines | 40 |
| min_peers | 10 |
| mad_floor | 0.02 |
| near_match_days | 30 |

| Type | Unit | Positives | Found | Recall | Raised | Precision | Decoys raised | Clean raised |
|---|---|---|---|---|---|---|---|---|
| duplicate_claim | claim | 60 | 60 | 100.0% | 60 | 100.0% | 0 of 60 | 0 of 39940 |
| unbundling | claim | 30 | 30 | 100.0% | 30 | 100.0% | 0 of 30 | 0 of 40000 |
| excess_units | claim | 30 | 30 | 100.0% | 30 | 100.0% | 0 of 30 | 0 of 40000 |
| date_anomaly | claim | 30 | 30 | 100.0% | 30 | 100.0% | 0 of 30 | 0 of 40000 |
| intensity_outlier | provider | 30 | 28 | 93.3% | 28 | 100.0% | 0 of 30 | 0 of 132 |

Line localisation (every labelled line cited by a finding):
- unbundling: 30 of 30 cases
- excess_units: 30 of 30 cases
- date_anomaly: 30 of 30 cases

Missed positives and false alarms (ids):
- duplicate_claim: missed none; decoys raised none; clean raised none
- unbundling: missed none; decoys raised none; clean raised none
- excess_units: missed none; decoys raised none; clean raised none
- date_anomaly: missed none; decoys raised none; clean raised none
- intensity_outlier: missed ['P0171', 'P0203']; decoys raised none; clean raised none

Providers with too little data to score: {'positive': 0, 'decoy': 0}

Near-match duplicate observations (claims, by label group):
- near_match_nearby_date: {'positive': 0, 'decoy': 30, 'clean': 6}
- near_match_other_provider: {'positive': 0, 'decoy': 30, 'clean': 28}
- group sizes: {'positive': 150, 'decoy': 150, 'clean': 39760}

Findings from checks with no labelled counterpart: none

Queue screens (flags by label group; confirmed = the tool also raised it):
- SCR01: {'flags_clean': 41, 'flags_positive': 30, 'confirmed_positive': 30, 'flags_decoy': 30}
- SCR02: {'flags_positive': 30, 'confirmed_positive': 30, 'flags_clean': 32, 'flags_decoy': 30}
- SCR03: {'flags_clean': 50, 'flags_positive': 30, 'confirmed_positive': 30, 'flags_decoy': 30}
- SCR04: {'flags_decoy': 89, 'flags_positive': 93, 'confirmed_positive': 87, 'flags_clean': 25}
- SCR05: {'flags_clean': 48, 'flags_positive': 30, 'confirmed_positive': 30, 'flags_decoy': 30}

wrote eval/scorecards/dev_20261019_untuned.json
