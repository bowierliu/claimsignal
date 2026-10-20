# Phase 7 E5: tools against the hand-built scenarios

Scenarios 20; exact match 20/20; expected findings found 11/11; false alarms 0; decoys that raised a finding 0.

| case | claim | decoy | expected | found | result |
|---|---|---|---|---|---|
| hb-01 | C9000001 |  | bundle_pair_without_exception | bundle_pair_without_exception | ok |
| hb-02 | C9000002 | yes | - | - | ok |
| hb-03 | C9000003 | yes | - | - | ok |
| hb-04 | C9000004 |  | units_above_line_limit | units_above_line_limit | ok |
| hb-05 | C9000005 | yes | - | - | ok |
| hb-06 | C9000006 |  | units_above_line_limit | units_above_line_limit | ok |
| hb-07 | C9000007 |  | line_date_outside_claim_window | line_date_outside_claim_window | ok |
| hb-08 | C9000008 |  | line_date_outside_claim_window | line_date_outside_claim_window | ok |
| hb-09 | C9000009 |  | claim_window_reversed, line_date_outside_claim_window | claim_window_reversed, line_date_outside_claim_window | ok |
| hb-10 | C9000010 | yes | - | - | ok |
| hb-11 | C9000011 |  | exact_duplicate | exact_duplicate | ok |
| hb-12 | C9000012 | yes | - | - | ok |
| hb-13 | C9000013 | yes | - | - | ok |
| hb-14 | C9000014 |  | diagnosis_pointer_out_of_range | diagnosis_pointer_out_of_range | ok |
| hb-15 | C2001000 |  | visit_mix_above_peer_range | visit_mix_above_peer_range | ok |
| hb-16 | C2002000 | yes | - | - | ok |
| hb-17 | C2003000 | yes | - | - | ok |
| hb-18 | C2004000 |  | visit_mix_above_peer_range | visit_mix_above_peer_range | ok |
| hb-19 | C2005000 | yes | - | - | ok |
| hb-20 | C2006000 | yes | - | - | ok |
