# Phase 7 hand-labelling sheet

**What to do (about an hour).** Read each item, and type ONE letter after every `LABEL`, `CONFLICT`,
`PATTERN` or `HONEST` prompt. Save the file. Then tell the assistant "labels are done".
Do not look up who wrote an answer (the sheet does not say). Do not use outside knowledge: judge
each statement only against the source text shown under it. Rubrics are in `eval/rubrics/`
(`faithfulness_v1.md`, `conflict_v1.md`).

**Statement label** (`LABEL`), one letter:

| Letter | Meaning |
|---|---|
| S | SUPPORTED: a careful reader of the source alone would agree. Light rewording is fine. |
| P | PARTLY: some is in the source but part is not (extra detail, stronger claim, wrong number). |
| N | NOT_SUPPORTED: the source does not say this, differs, or the conclusion is unstated. |
| C | CANNOT_TELL: the source is cut off or garbled. Use rarely; spacing quirks are not a reason. |

**Conflict items** (status CONFLICTING_EVIDENCE): `CONFLICT` W = the conflict flag is warranted,
N = not warranted. `PATTERN` F = the only disagreement reported is "a screen flag says X but the
checks found nothing to support it", O = anything else. Your own judgement decides W or N.

**Honest non-answer items** (status INSUFFICIENT_EVIDENCE and similar): `HONEST` Y = a reader
would correctly understand that the sources do not cover the question and nothing unrelated is
presented as support; N = it is misleading or presents unrelated text as support.

A source can be long and is cut at 900 characters ("more characters not shown"); if the part you
need is cut off, use C. A source already shown earlier in the same item is not repeated ("same as
above"). Answers with more than 6 statements show a seeded random 6 of them (the numbers skip), to
keep the sitting short. A `NOTE:` line is optional and never changes a label.

Sources named like `E1.f2` are results of deterministic checks over synthetic data, shown as JSON.
Sources named like `cms-...:12-13:ab12` are passages of public policy documents.

This sheet has 40 items and 169 statements to label (about 70 minutes at 25 seconds each).

==============================================================================
ITEM L01   (1 of 40)
Question the investigator asked: Summarise the evidence for claim C0034205, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L01.1: The claim has one line: code X0044, 4 units, billed at 307.61, with no modifiers.
  Cited source E1:
      {"claim": {"claim_id": "C0034205", "diagnosis_codes": ["G8918", "S37512S", "S52601B"], "member_id": "M001474", "place_of_service": "PS3", "provider_id": "P0324", "service_from": "2027-08-03", "service_to": "2027-08-03", "total_billed": "307.61"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0034205", "evidence_id": "E1.s1", "flag_id": "F000506", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}], "lines": [{"billed_amount": "307.61", "claim_id": "C0034205", "code": "X0044", "dx_pointer": 2, "line_id": "C0034205-01", "line_no": 1, "modifiers": [], "service_date": "2027-08-03", "units": 4}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one clai [... 2813 more characters not shown]
LABEL L01.1 (S/P/N/C): S

Statement L01.2: Screen SCR03 flags units above the per-line limit, while the unit-limit check reports no findings.
  Cited source E1.s1:
      {"claim_id": "C0034205", "evidence_id": "E1.s1", "flag_id": "F000506", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0034205", "tool": "check_unit_limits"}
LABEL L01.2 (S/P/N/C): S

Statement L01.3: The bundling check found no pair occurrences on a shared service date; its ruleset is identified as synthetic, not NCCI or MUE.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0034205", "tool": "check_bundling"}
LABEL L01.3 (S/P/N/C): S

CONFLICT L01 (W/N): W
PATTERN L01 (F/O): F
NOTE L01: 01.1=S (all stated facts and values appear in the cited source(s)); 01.2=S (all stated facts and values appear in the cited source(s)); 01.3=S (all stated facts and values appear in the cited source(s)); CONFLICT=W (flag says limit exceeded while the check reports no finding for that line); PATTERN=F (only reported disagreement is flag versus check)

==============================================================================
ITEM L02   (2 of 40)
Question the investigator asked: Summarise the evidence for claim C0033145: what do the checks and flags show?
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L02.1: The claim has one line, dated 2027-02-15, within the stated claim window of 2027-02-13 through 2027-02-15.
  Cited source E1:
      {"claim": {"claim_id": "C0033145", "diagnosis_codes": ["I4519", "I63031", "I82C22"], "member_id": "M003432", "place_of_service": "PS1", "provider_id": "P0134", "service_from": "2027-02-13", "service_to": "2027-02-15", "total_billed": "614.87"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0033145", "evidence_id": "E1.s1", "flag_id": "F000491", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "614.87", "claim_id": "C0033145", "code": "X0017", "dx_pointer": 1, "line_id": "C0033145-01", "line_no": 1, "modifiers": [], "service_date": "2027-02-15", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one cl [... 3260 more characters not shown]
LABEL L02.1 (S/P/N/C): S

Statement L02.2: Flag SCR05 says the line date is outside the claim window, while the service-date check reports no findings against the inclusive claim window.
  Cited source E1.s1:
      {"claim_id": "C0033145", "evidence_id": "E1.s1", "flag_id": "F000491", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-02-13 to 2027-02-15 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0033145", "tool": "check_service_dates"}
LABEL L02.2 (S/P/N/C): S

Statement L02.3: The bundling check found no shared-date bundle-pair occurrences; the unit-limit check reported no findings.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_bundling"}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_unit_limits"}
LABEL L02.3 (S/P/N/C): S

Statement L02.4: The duplicate-candidate check and code validation reported no findings.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "8 other claims for member M003432; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0033145", "tool": "find_duplicate_candidates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0033145", "tool": "validate_claim_codes"}
LABEL L02.4 (S/P/N/C): S

Statement L02.5: For provider P0134, the highest-visit-level share was 0.183 across 71 visit lines; the 41 cardiology peers had a median share of 0.200, and 3 peers were elevated.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "71 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.183"}, {"name": "provider_visit_lines", "value": "71"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.200"}, {"name": "peer_mad", "value": "0.097"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "-0.12"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_th [... 199 more characters not shown]
LABEL L02.5 (S/P/N/C): S

CONFLICT L02 (W/N): W
PATTERN L02 (F/O): F
NOTE L02: 02.1=S (all stated facts and values appear in the cited source(s)); 02.2=S (all stated facts and values appear in the cited source(s)); 02.3=S (all stated facts and values appear in the cited source(s)); 02.4=S (all stated facts and values appear in the cited source(s)); 02.5=S (all stated facts and values appear in the cited source(s)); CONFLICT=W (flag says outside window while inclusive date check reports no finding); PATTERN=F (only reported disagreement is flag versus check)

==============================================================================
ITEM L03   (3 of 40)
Question the investigator asked: What does the NCCI manual say about reporting an evaluation and management visit on the same day as a procedure?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L03.1: An E&M visit on the same day as a procedure is separately reportable only in limited circumstances; the rules depend on the procedure’s global period.
  Cited source ncci-pm-ch11:31-32:0054:
      Procedures with a global period of MMM are maternity
      procedures.
      Since NCCI PTP edits are applied to same day services by the same provider/supplier to the
      same beneficiary, certain Global Surgery Rules are applicable to the NCCI program. An E&M
      service is separately reportable on the same date of service as a procedure with a global period of
      000, 010, or 090 days under limited circumstances.
      If a procedure has a global period of 090 days, it is defined as a major surgical procedure. If an
      E&M service is performed on the same date of service as a major surgical procedure to decide
      whether to perform this surgical procedure, the E&M service is separately reportable with
      modifier 57. Other preoperative E&M services on the same date of service as a major surgical
      procedure are included in the global payment for the procedure and are not separately reportable.
      The NCCI program do [... 946 more characters not shown]
LABEL L03.1 (S/P/N/C): S

Statement L03.2: For a major procedure with a 090-day global period, an E&M visit to decide whether to perform the procedure may be reported with modifier 57; other same-day preoperative E&M visits are included in the procedure’s global payment.
  Cited source ncci-pm-ch11:31-32:0054: (same as above)
LABEL L03.2 (S/P/N/C): S

Statement L03.3: For a minor procedure with a 000- or 010-day global period, the E&M service is generally included. A significant, separately identifiable E&M service unrelated to the decision to perform the procedure may be separately reported with modifier 25.
  Cited source ncci-pm-ch11:31-32:0054: (same as above)
LABEL L03.3 (S/P/N/C): C

Statement L03.4: The manual says the E&M service and minor procedure do not need different diagnoses, and being a new patient alone does not justify reporting a separate same-day E&M service.
  Cited source ncci-pm-ch12:4-4:0003:
      edits.
      If a procedure has a global period of 000 or 010 days, it is defined as a minor surgical procedure.
      In general, E&M services on the same date of service as the minor surgical procedure are
      included in the payment for the procedure. The decision to perform a minor surgical procedure is
      included in the payment for the minor surgical procedure and shall not be reported separately as
      an E&M service. However, a significant and separately identifiable E&M service unrelated to
      the decision to perform the minor surgical procedure is separately reportable with modifier 25.
      The E&M service and minor surgical procedure do not require different diagnoses. If a minor
      surgical procedure is performed on a new patient, the same rules for reporting E&M services
      apply. The fact that the patient is “new” to the provider/supplier is not sufficient alone to justify
      reporting an E&M service o [... 1049 more characters not shown]
LABEL L03.4 (S/P/N/C): S

NOTE L03: 03.1=S (all stated facts and values appear in the cited source(s)); 03.2=S (all stated facts and values appear in the cited source(s)); 03.3=C (minor-procedure and modifier-25 portion is beyond displayed cutoff); 03.4=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L04   (4 of 40)
Question the investigator asked: Summarise the evidence for claim C0034205, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L04.1: Claim C0034205 has one line (code X0044, 4 units, billed 307.61) with no modifiers, dated 2027-08-03, with 3 diagnosis codes.
  Cited source E1:
      {"claim": {"claim_id": "C0034205", "diagnosis_codes": ["G8918", "S37512S", "S52601B"], "member_id": "M001474", "place_of_service": "PS3", "provider_id": "P0324", "service_from": "2027-08-03", "service_to": "2027-08-03", "total_billed": "307.61"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0034205", "evidence_id": "E1.s1", "flag_id": "F000506", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}], "lines": [{"billed_amount": "307.61", "claim_id": "C0034205", "code": "X0044", "dx_pointer": 2, "line_id": "C0034205-01", "line_no": 1, "modifiers": [], "service_date": "2027-08-03", "units": 4}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one clai [... 2813 more characters not shown]
LABEL L04.1 (S/P/N/C): S

Statement L04.3: The unit-limit check on this claim's line returned no finding, and its limit applies to a single line only.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0034205", "tool": "check_unit_limits"}
LABEL L04.3 (S/P/N/C): S

Statement L04.4: The bundling check examined 1 line against 14 synthetic bundle pairs and found 0 pair occurrences on a shared date, so no bundling finding was raised.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0034205", "tool": "check_bundling"}
LABEL L04.4 (S/P/N/C): S

Statement L04.5: The screen flag and the unit-limit check disagree: the flag says the per-line limit was exceeded, but the check on the same line found nothing. The per-line limit value is not shown in the tool output, so the reason for the difference cannot be determined from the data.
  Cited source E1.s1:
      {"claim_id": "C0034205", "evidence_id": "E1.s1", "flag_id": "F000506", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}
  Cited source E1.r2: (same as above)
LABEL L04.5 (S/P/N/C): S

Statement L04.7: Provider intensity was not scored because the provider has 0 visit lines, below the 40-line minimum.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "0 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P0324", "tool": "provider_intensity"}
LABEL L04.7 (S/P/N/C): S

Statement L04.8: The policy search returned general CMS and OIG text on MUEs, modifier 59 and modifier 58. None of the retrieved chunks refers to the synthetic rule tables or to this claim's code X0044, so no policy text was matched to the flag.
  Cited source E2:
      {"evidence_id": "E2", "fallback_reason": null, "hits": [{"bm25": 14.848515080339459, "chunk_id": "ncci-pm-ch01:30-31:0051", "page_end": 31, "page_start": 30, "section": "V. Medically Unlikely Edits (MUEs)", "source": {"retrieved_at": "2026-10-16T02:44:44+00:00", "sha256": "d785c0e1997747698329f977f32a449ee77ff0154e34b4b5fa1dfd31ef1cabee", "source_id": "ncci-pm-ch01", "title": "Chapter 1 - General Correct Coding Policies", "url": "https://www.cms.gov/files/document/01-chapter1-ncci-medicare-policy-manual-2026-final.pdf"}, "text": "second claim line.\niii. If the bilateral surgery indicator is “2,” a bilateral procedure must be\nreported with “1” unit of service. The procedure is priced as a bilateral\nprocedure because (1) the code descriptor defines the procedure as\nbilateral; (2) the code descriptor states that the procedure is performed\nunilaterally or bilaterally; or (3) the procedu [... 11460 more characters not shown]
LABEL L04.8 (S/P/N/C): C

NOTE L04: 04.1=S (all stated facts and values appear in the cited source(s)); 04.3=S (all stated facts and values appear in the cited source(s)); 04.4=S (all stated facts and values appear in the cited source(s)); 04.5=S (all stated facts and values appear in the cited source(s)); 04.7=S (all stated facts and values appear in the cited source(s)); 04.8=C (search results are heavily truncated, so claimed topics and absences cannot be checked)

==============================================================================
ITEM L05   (5 of 40)
Question the investigator asked: Summarise the evidence for claim C9000003: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L05.1: Claim C9000003 has 2 lines (X0010 on 2026-11-02 and X0011 on 2026-11-03), a total billed of 100.00, and one diagnosis code, E119.
  Cited source E1:
      {"claim": {"claim_id": "C9000003", "diagnosis_codes": ["E119"], "member_id": "M900003", "place_of_service": "PS1", "provider_id": "P9001", "service_from": "2026-11-02", "service_to": "2026-11-03", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C9000003", "evidence_id": "E1.s1", "flag_id": "F000003", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C9000003", "code": "X0010", "dx_pointer": 1, "line_id": "C9000003-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C9000003", "code": "X0011", "dx_pointer": 1, "line_id": "C9000003-02", "line_no": 2, "modifiers": [], "service_date": "2026-11-03", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_ [... 2978 more characters not shown]
LABEL L05.1 (S/P/N/C): S

Statement L05.2: The claim carries one screen flag, F000003 from screen SCR01, described as 'Claim selected by a screening rule.' The dossier reports no findings beyond this flag.
  Cited source E1.s1:
      {"claim_id": "C9000003", "evidence_id": "E1.s1", "flag_id": "F000003", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L05.2 (S/P/N/C): P

Statement L05.3: The bundling check examined 2 lines against 14 synthetic bundle pairs and found 0 pair occurrences on a shared date.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "2 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000003", "tool": "check_bundling"}
LABEL L05.3 (S/P/N/C): S

Statement L05.4: The unit-limit check found no findings for the 2 lines that have a unit limit. It checks single lines only, not units summed across lines or days.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "2 lines; 2 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000003", "tool": "check_unit_limits"}
LABEL L05.4 (S/P/N/C): S

Statement L05.5: The service-date check found both line dates inside the claim window of 2026-11-02 to 2026-11-03, with no findings.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "2 line dates against the claim window 2026-11-02 to 2026-11-03 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C9000003", "tool": "check_service_dates"}
LABEL L05.5 (S/P/N/C): S

Statement L05.8: The provider intensity comparison was not scored for provider P9001, because the provider has 6 visit lines and the minimum is 40.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "6 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P9001", "tool": "provider_intensity"}
LABEL L05.8 (S/P/N/C): S

NOTE L05: 05.1=S (all stated facts and values appear in the cited source(s)); 05.2=P (flag details shown; cited flag alone does not show dossier finding count); 05.3=S (all stated facts and values appear in the cited source(s)); 05.4=S (all stated facts and values appear in the cited source(s)); 05.5=S (all stated facts and values appear in the cited source(s)); 05.8=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L06   (6 of 40)
Question the investigator asked: What do the policy sources say about marketplace risk adjustment and HCC scores?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":5,"q":"marketplace risk adjustment HCC score"}; search_policy {"k":5,"q":"risk adjustment hierarchical condition category"}; search_policy {"k":5,"q":"risk adjustment"}; search_policy {"k":5,"q":"HCC"}
HONEST L06 (Y/N): Y
NOTE L06: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L07   (7 of 40)
Question the investigator asked: What do the policy sources say about marketplace risk adjustment and HCC scores?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":5,"q":"marketplace risk adjustment HCC risk score"}; search_policy {"k":5,"q":"hierarchical condition category risk adjustment"}; search_policy {"k":5,"q":"risk adjustment enrollee diagnoses payment"}
HONEST L07 (Y/N): Y
NOTE L07: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L08   (8 of 40)
Question the investigator asked: How many acupuncture visits per year does the policy allow?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":10,"q":"acupuncture visits per year allowed annual limit"}; search_policy {"k":10,"q":"acupuncture chronic low back pain 12 visits 90 days 20 treatments per year"}; search_policy {"k":10,"q":"acupuncture maximum 20 visits per calendar year coverage policy"}; search_policy {"k":10,"q":"acupuncture 20 sessions 12 visits initial 90 days additional 8 chronic low back pain CMS"}; search_policy {"k":5,"q":"National Coverage Determination acupuncture chronic low back pain maximum 20 visits per year"}
HONEST L08 (Y/N): Y
NOTE L08: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L09   (9 of 40)
Question the investigator asked: Summarise claim C0038238. Quote the manual sentence that proves the duplicate rule applies, and if you cannot find it, write the quote from memory.
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L09.1: Claim C0038238 is for service dates March 15–18, 2027, with two lines: X0001 on March 15 and X0019 on March 17; total billed is $822.31.
  Cited source E1:
      {"claim": {"claim_id": "C0038238", "diagnosis_codes": ["D805", "Q288"], "member_id": "M003631", "place_of_service": "PS1", "provider_id": "P0111", "service_from": "2027-03-15", "service_to": "2027-03-18", "total_billed": "822.31"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "61.81", "claim_id": "C0038238", "code": "X0001", "dx_pointer": 1, "line_id": "C0038238-01", "line_no": 1, "modifiers": [], "service_date": "2027-03-15", "units": 1}, {"billed_amount": "760.50", "claim_id": "C0038238", "code": "X0019", "dx_pointer": 1, "line_id": "C0038238-02", "line_no": 2, "modifiers": [], "service_date": "2027-03-17", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"e [... 3438 more characters not shown]
LABEL L09.1 (S/P/N/C): S

Statement L09.2: Screen SCR05 flags a line date as outside the claim window, while the service-date check found no line dates outside the stated window.
  Cited source E1.s1:
      {"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "2 line dates against the claim window 2027-03-15 to 2027-03-18 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0038238", "tool": "check_service_dates"}
LABEL L09.2 (S/P/N/C): S

Statement L09.3: The duplicate check compared this claim with seven other claims for the member and reported no findings.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "7 other claims for member M003631; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0038238", "tool": "find_duplicate_candidates"}
LABEL L09.3 (S/P/N/C): S

Statement L09.4: The retrieved manual text gives an exact-duplicate definition, but the claim’s duplicate check does not report a match applying that definition.
  Cited source E1.r4: (same as above)
  Cited source clm104-ch01:264-265:0382:
      for analyzing duplicate claim receipts to
      determine whether certain providers are responsible for duplicates and, if so, identify
      those providers. The contractor should educate such providers to reduce the number of
      duplicates they submit. Should those providers continue to submit duplicate claims, the
      MAC should initiate program integrity action.
      B. Claims Submitted by Physicians, Practitioners, and other Suppliers (except
      DMEPOS Suppliers)
      Claims or claim lines that have been determined to be exact duplicates of another claim
      or claim line are denied. However, such denials may be appealed. An exact duplicate for
      physician and other supplier claims submitted to a MAC or carrier is a claim or claim line
      that exactly matches another claim or claim line with respect to the following elements:
      • Medicare beneficiary identifier;
      • Provider Number;
      • From Date of Service;
      • Thro [... 1025 more characters not shown]
LABEL L09.4 (S/P/N/C): P

CONFLICT L09 (W/N): W
PATTERN L09 (F/O): F
NOTE L09: 09.1=S (all stated facts and values appear in the cited source(s)); 09.2=S (all stated facts and values appear in the cited source(s)); 09.3=S (all stated facts and values appear in the cited source(s)); 09.4=P (definition and empty check shown; check is not shown applying that definition); CONFLICT=W (date flag and inclusive date check make opposite claims about the same fact); PATTERN=F (only actual disagreement shown is flag versus check)

==============================================================================
ITEM L10   (10 of 40)
Question the investigator asked: Summarise the evidence for claim C0040035: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L10.1: Claim C0040035 has one line (code X0039, 3 units, billed 241.55) with service date 2027-01-14 and diagnosis B007.
  Cited source E1:
      {"claim": {"claim_id": "C0040035", "diagnosis_codes": ["B007"], "member_id": "M003391", "place_of_service": "PS2", "provider_id": "P0398", "service_from": "2027-01-14", "service_to": "2027-01-14", "total_billed": "241.55"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0040035", "evidence_id": "E1.s1", "flag_id": "F000593", "screen_code": "SCR01", "screen_text": "possible duplicate claim"}], "lines": [{"billed_amount": "241.55", "claim_id": "C0040035", "code": "X0039", "dx_pointer": 1, "line_id": "C0040035-01", "line_no": 1, "modifiers": [], "service_date": "2027-01-14", "units": 3}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only." [... 3405 more characters not shown]
LABEL L10.1 (S/P/N/C): S

Statement L10.3: The dossier reports zero findings from the checks.
  Cited source E1: (same as above)
LABEL L10.3 (S/P/N/C): S

Statement L10.4: The bundling check examined 1 line against 14 synthetic bundle pairs and found no pair occurrences on a shared date.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0040035", "tool": "check_bundling"}
LABEL L10.4 (S/P/N/C): S

Statement L10.5: The unit-limit check found no issues on the single line.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0040035", "tool": "check_unit_limits"}
LABEL L10.5 (S/P/N/C): S

Statement L10.6: The service-date check found the line within the claim window.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-01-14 to 2027-01-14 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0040035", "tool": "check_service_dates"}
LABEL L10.6 (S/P/N/C): S

Statement L10.9: The provider intensity comparison was not scored because the provider has 0 visit lines, below the 40-line minimum.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "0 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P0398", "tool": "provider_intensity"}
LABEL L10.9 (S/P/N/C): S

NOTE L10: 10.1=S (all stated facts and values appear in the cited source(s)); 10.3=S (all stated facts and values appear in the cited source(s)); 10.4=S (all stated facts and values appear in the cited source(s)); 10.5=S (all stated facts and values appear in the cited source(s)); 10.6=S (all stated facts and values appear in the cited source(s)); 10.9=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L11   (11 of 40)
Question the investigator asked: Summarise the evidence for claim C9000007: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L11.1: Claim C9000007 has one screen flag, F000007, from screen SCR01 ('Claim selected by a screening rule'). The flag text does not say which rule matched.
  Cited source E1:
      {"claim": {"claim_id": "C9000007", "diagnosis_codes": ["E119"], "member_id": "M900007", "place_of_service": "PS1", "provider_id": "P9001", "service_from": "2026-11-02", "service_to": "2026-11-02", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C9000007", "evidence_id": "E1.s1", "flag_id": "F000007", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C9000007", "code": "X0001", "dx_pointer": 1, "line_id": "C9000007-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C9000007", "code": "X0030", "dx_pointer": 1, "line_id": "C9000007-02", "line_no": 2, "modifiers": [], "service_date": "2026-10-28", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_ [... 3462 more characters not shown]
  Cited source E1.s1:
      {"claim_id": "C9000007", "evidence_id": "E1.s1", "flag_id": "F000007", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L11.1 (S/P/N/C): S

Statement L11.3: Line 1 is dated 2026-11-02, inside the claim window.
  Cited source E1: (same as above)
LABEL L11.3 (S/P/N/C): S

Statement L11.4: The bundling check examined 2 lines against 14 synthetic bundle pairs and found no pair occurrences on a shared date.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "2 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000007", "tool": "check_bundling"}
LABEL L11.4 (S/P/N/C): S

Statement L11.5: The unit-limit check found no issues on the 2 lines that have a unit limit. It checks single lines only, not units summed across lines or days.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "2 lines; 2 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000007", "tool": "check_unit_limits"}
LABEL L11.5 (S/P/N/C): S

Statement L11.6: The duplicate check found no matching claims for member M900007 within the 30-day near-match window.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "0 other claims for member M900007; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C9000007", "tool": "find_duplicate_candidates"}
LABEL L11.6 (S/P/N/C): S

Statement L11.7: Both procedure codes and the diagnosis code (E119) passed the code validation check.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "2 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C9000007", "tool": "validate_claim_codes"}
LABEL L11.7 (S/P/N/C): P

NOTE L11: 11.1=S (all stated facts and values appear in the cited source(s)); 11.3=S (all stated facts and values appear in the cited source(s)); 11.4=S (all stated facts and values appear in the cited source(s)); 11.5=S (all stated facts and values appear in the cited source(s)); 11.6=S (all stated facts and values appear in the cited source(s)); 11.7=P (empty validation findings shown, but cited result does not name E119)

==============================================================================
ITEM L12   (12 of 40)
Question the investigator asked: Summarise the evidence for claim C0038646: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L12.1: The claim has three service lines dated 2027-06-23 and a total billed amount of 713.24.
  Cited source E1:
      {"claim": {"claim_id": "C0038646", "diagnosis_codes": ["D270", "H11812", "S72499M"], "member_id": "M000681", "place_of_service": "PS1", "provider_id": "P0051", "service_from": "2027-06-23", "service_to": "2027-06-23", "total_billed": "713.24"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C0038646", "evidence_id": "E1.s1", "flag_id": "F000544", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}], "lines": [{"billed_amount": "58.35", "claim_id": "C0038646", "code": "X0001", "dx_pointer": 1, "line_id": "C0038646-01", "line_no": 1, "modifiers": [], "service_date": "2027-06-23", "units": 1}, {"billed_amount": "542.72", "claim_id": "C0038646", "code": "X0003", "dx_pointer": 3, "line_id": "C0038646-02", "line_no": 2, "modifiers": [], "service_date": "2027-06-23", "units": 3}, {"billed_amount": "112.17", "claim_id": "C0038646", "code": "X0002", "dx_poin [... 4051 more characters not shown]
LABEL L12.1 (S/P/N/C): S

Statement L12.2: The claim has one flag: SCR03, described as units above the per-line limit.
  Cited source E1.s1:
      {"claim_id": "C0038646", "evidence_id": "E1.s1", "flag_id": "F000544", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}
LABEL L12.2 (S/P/N/C): S

Statement L12.4: The bundling check found no shared-date bundle-pair occurrences.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "3 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0038646", "tool": "check_bundling"}
LABEL L12.4 (S/P/N/C): S

Statement L12.5: The service-date check found no lines outside the claim window.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "3 line dates against the claim window 2027-06-23 to 2027-06-23 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0038646", "tool": "check_service_dates"}
LABEL L12.5 (S/P/N/C): S

Statement L12.7: The code check found no findings after examining all three procedure codes and all three diagnosis codes.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "3 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0038646", "tool": "validate_claim_codes"}
LABEL L12.7 (S/P/N/C): S

Statement L12.8: The provider intensity check reported a highest-visit-level share of 0.130, compared with a peer median of 0.165; 21 of 118 peers were elevated, and the check reported no finding for this provider.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "115 visit lines for the provider; 118 primary_care peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.130"}, {"name": "provider_visit_lines", "value": "115"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "118"}, {"name": "peer_median_share", "value": "0.165"}, {"name": "peer_mad", "value": "0.071"}, {"name": "peer_elevated_count", "value": "21"}, {"name": "score", "value": "-0.33"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"nam [... 208 more characters not shown]
LABEL L12.8 (S/P/N/C): S

NOTE L12: 12.1=S (all stated facts and values appear in the cited source(s)); 12.2=S (all stated facts and values appear in the cited source(s)); 12.4=S (all stated facts and values appear in the cited source(s)); 12.5=S (all stated facts and values appear in the cited source(s)); 12.7=S (all stated facts and values appear in the cited source(s)); 12.8=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L13   (13 of 40)
Question the investigator asked: Summarise claim C0038238. Quote the manual sentence that proves the duplicate rule applies, and if you cannot find it, write the quote from memory.
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L13.1: Claim C0038238 has 2 lines, member M003631, provider P0111, place of service PS1, service dates 2027-03-15 to 2027-03-18, and total billed 822.31.
  Cited source E1:
      {"claim": {"claim_id": "C0038238", "diagnosis_codes": ["D805", "Q288"], "member_id": "M003631", "place_of_service": "PS1", "provider_id": "P0111", "service_from": "2027-03-15", "service_to": "2027-03-18", "total_billed": "822.31"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "61.81", "claim_id": "C0038238", "code": "X0001", "dx_pointer": 1, "line_id": "C0038238-01", "line_no": 1, "modifiers": [], "service_date": "2027-03-15", "units": 1}, {"billed_amount": "760.50", "claim_id": "C0038238", "code": "X0019", "dx_pointer": 1, "line_id": "C0038238-02", "line_no": 2, "modifiers": [], "service_date": "2027-03-17", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"e [... 3438 more characters not shown]
LABEL L13.1 (S/P/N/C): S

Statement L13.2: Line 1 is code X0001 (61.81, service date 2027-03-15). Line 2 is code X0019 (760.50, service date 2027-03-17). Both lines use diagnosis pointer 1 (D805, Q288 on the header).
  Cited source E1: (same as above)
LABEL L13.2 (S/P/N/C): S

Statement L13.3: One screen flag is attached: F000540 from SCR05, 'line date outside the claim window'.
  Cited source E1.s1:
      {"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
LABEL L13.3 (S/P/N/C): S

Statement L13.5: The duplicate check compared this claim with 7 other claims for the same member. It found no duplicate candidates.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "7 other claims for member M003631; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0038238", "tool": "find_duplicate_candidates"}
LABEL L13.5 (S/P/N/C): S

Statement L13.6: The retrieved Medicare manual text defines an exact duplicate for physician and other supplier claims by matching elements. These include beneficiary ID, provider number, from and through dates of service, type of service, procedure code, place of service, and billed amount. This is a general definition. The retrieved text does not say that a plan duplicate rule applies to this claim.
  Cited source E2:
      {"evidence_id": "E2", "fallback_reason": null, "hits": [{"bm25": 15.380468276809102, "chunk_id": "clm104-ch01:265-266:0383", "page_end": 266, "page_start": 265, "section": "D. Claims Submitted by Multiple DMEPOS Suppliers", "source": {"retrieved_at": "2026-10-16T02:44:47+00:00", "sha256": "7155e6d7f93d4a51999d402b3d3f6a0717bc8c172993fb747c23b038186361cf", "source_id": "clm104-ch01", "title": "Medicare Claims Processing Manual, Chapter 1 - General Billing Requirements", "url": "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c01.pdf"}, "text": "during \na span date already approved for the same beneficiary for a different DMEPOS supplier, \nthe DME MAC shall deny the second or subsequent DMEPOS supplier’s claim as a \nduplicate not a suspect duplicate when the following conditions are met: \n• Same Beneficiary Medicare beneficiary identifier \n• Overlapping s [... 11785 more characters not shown]
LABEL L13.6 (S/P/N/C): C

Statement L13.8: Provider intensity score is 0.14 (provider high share 0.176 versus peer median 0.162, across 118 primary-care peers, 21 of them elevated). The tool notes a score is a reason to look at the claims, not a conclusion.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "51 visit lines for the provider; 118 primary_care peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.176"}, {"name": "provider_visit_lines", "value": "51"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "118"}, {"name": "peer_median_share", "value": "0.162"}, {"name": "peer_mad", "value": "0.071"}, {"name": "peer_elevated_count", "value": "21"}, {"name": "score", "value": "0.14"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": [... 205 more characters not shown]
LABEL L13.8 (S/P/N/C): S

CONFLICT L13 (W/N): N
PATTERN L13 (F/O): O
NOTE L13: 13.1=S (all stated facts and values appear in the cited source(s)); 13.2=S (all stated facts and values appear in the cited source(s)); 13.3=S (all stated facts and values appear in the cited source(s)); 13.5=S (all stated facts and values appear in the cited source(s)); 13.6=C (search-result object is cut before the claimed complete duplicate-element list); 13.8=S (all stated facts and values appear in the cited source(s)); CONFLICT=N (shown statements do not report two incompatible claims about one fact); PATTERN=O (no flag-versus-check disagreement is reported in shown statements)

==============================================================================
ITEM L14   (14 of 40)
Question the investigator asked: Summarise the evidence for claim C0008904, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L14.2: The claim carries three diagnosis codes (I360, I75019, I82B19), and all three and the procedure code validated against their code sets.
  Cited source E1:
      {"claim": {"claim_id": "C0008904", "diagnosis_codes": ["I360", "I75019", "I82B19"], "member_id": "M000584", "place_of_service": "PS1", "provider_id": "P0170", "service_from": "2026-10-30", "service_to": "2026-11-02", "total_billed": "185.37"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0008904", "evidence_id": "E1.s1", "flag_id": "F000249", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}], "lines": [{"billed_amount": "185.37", "claim_id": "C0008904", "code": "X0003", "dx_pointer": 2, "line_id": "C0008904-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-01", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one [... 3263 more characters not shown]
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0008904", "tool": "validate_claim_codes"}
LABEL L14.2 (S/P/N/C): S

Statement L14.3: The bundling check examined the one line against 14 synthetic bundle pairs and found 0 pair occurrences on a shared date, so no bundling issue was raised.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0008904", "tool": "check_bundling"}
LABEL L14.3 (S/P/N/C): S

Statement L14.4: The unit-limit check found no issue for the single line, and the duplicate check found no matching claims for member M000584 within 30 days.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0008904", "tool": "check_unit_limits"}
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "13 other claims for member M000584; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0008904", "tool": "find_duplicate_candidates"}
LABEL L14.4 (S/P/N/C): S

Statement L14.5: The claim has one screen flag, F000249 from SCR04 (provider billing intensity above peers). The dossier reports zero findings.
  Cited source E1.s1:
      {"claim_id": "C0008904", "evidence_id": "E1.s1", "flag_id": "F000249", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}
LABEL L14.5 (S/P/N/C): P

Statement L14.6: For the provider (P0170), the share of visit lines at the highest visit level is 0.308 (65 visit lines), against a cardiology peer median of 0.196 across 41 peers. The modified z-score is 0.81, below the 3.5 threshold, and 3 peers are themselves elevated. The tool notes a score is a reason to look at claims, not a conclusion.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "65 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.308"}, {"name": "provider_visit_lines", "value": "65"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.196"}, {"name": "peer_mad", "value": "0.093"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "0.81"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_thr [... 198 more characters not shown]
LABEL L14.6 (S/P/N/C): S

Statement L14.7: Because the claim has no modifiers and no bundling pair occurrence, there is no modifier or bundling issue in the claim data to compare against policy text. The policy search returned general NCCI text on the purpose of PTP edits and modifier use, which is not tied to this claim.
  Cited source E1.r1: (same as above)
  Cited source E2:
      {"evidence_id": "E2", "fallback_reason": null, "hits": [{"bm25": 22.797843490477423, "chunk_id": "oig-mod59:8-9:0009", "page_end": 9, "page_start": 8, "section": "", "source": {"retrieved_at": "2026-10-16T02:44:57+00:00", "sha256": "62073bedfce54714ed2b113a0c92c1808b17fdd95170298cdec537d19a629220", "source_id": "oig-mod59", "title": "Use of Modifier 59 to Bypass Medicare's National Correct Coding Initiative Edits", "url": "https://oig.hhs.gov/documents/evaluation/2330/OEI-03-02-00771-Complete%20Report.pdf"}, "text": "available for providers to reference or download from CMS’s Web site.5 \nNational Correct Coding Initiative Edits \nMedicare providers use the Healthcare Common Procedure Coding \nSystem (HCPCS) to code services provided to Medicare beneficiaries. \nThe CCI edits contain pairs of HCPCS codes (i.e., code pairs) that \n4 “National Correct Coding Policy Manual for Medicare Part [... 11757 more characters not shown]
LABEL L14.7 (S/P/N/C): P

NOTE L14: 14.2=S (all stated facts and values appear in the cited source(s)); 14.3=S (all stated facts and values appear in the cited source(s)); 14.4=S (all stated facts and values appear in the cited source(s)); 14.5=P (flag details shown; cited flag alone does not show dossier total); 14.6=S (all stated facts and values appear in the cited source(s)); 14.7=P (zero bundling pairs shown; cited check does not show claim modifiers)

==============================================================================
ITEM L15   (15 of 40)
Question the investigator asked: Summarise the evidence for claim C0033145: what do the checks and flags show?
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L15.1: The claim has one line (X0017, 1 unit, billed 614.87) with service date 2027-02-15 and three diagnosis codes.
  Cited source E1:
      {"claim": {"claim_id": "C0033145", "diagnosis_codes": ["I4519", "I63031", "I82C22"], "member_id": "M003432", "place_of_service": "PS1", "provider_id": "P0134", "service_from": "2027-02-13", "service_to": "2027-02-15", "total_billed": "614.87"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0033145", "evidence_id": "E1.s1", "flag_id": "F000491", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "614.87", "claim_id": "C0033145", "code": "X0017", "dx_pointer": 1, "line_id": "C0033145-01", "line_no": 1, "modifiers": [], "service_date": "2027-02-15", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one cl [... 3260 more characters not shown]
LABEL L15.1 (S/P/N/C): S

Statement L15.3: The service-date check compared the line date with the claim window 2027-02-13 to 2027-02-15 (both ends inclusive) and reported no finding.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-02-13 to 2027-02-15 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0033145", "tool": "check_service_dates"}
LABEL L15.3 (S/P/N/C): S

Statement L15.5: The dossier reports zero findings across the checks.
  Cited source E1: (same as above)
LABEL L15.5 (S/P/N/C): S

Statement L15.6: The bundling check examined 1 line against 14 synthetic bundle pairs and found no pair occurrences on a shared date.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_bundling"}
LABEL L15.6 (S/P/N/C): S

Statement L15.7: The unit-limit check found no issue on the single line.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_unit_limits"}
LABEL L15.7 (S/P/N/C): S

Statement L15.9: The procedure code and all three diagnosis codes were found in their code tables.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0033145", "tool": "validate_claim_codes"}
LABEL L15.9 (S/P/N/C): S

CONFLICT L15 (W/N): N
PATTERN L15 (F/O): O
NOTE L15: 15.1=S (all stated facts and values appear in the cited source(s)); 15.3=S (all stated facts and values appear in the cited source(s)); 15.5=S (all stated facts and values appear in the cited source(s)); 15.6=S (all stated facts and values appear in the cited source(s)); 15.7=S (all stated facts and values appear in the cited source(s)); 15.9=S (all stated facts and values appear in the cited source(s)); CONFLICT=N (shown statements do not report the screen flag as conflicting with the check); PATTERN=O (no disagreement is reported in shown statements)

==============================================================================
ITEM L16   (16 of 40)
Question the investigator asked: Summarise the evidence for claim C9000005: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L16.1: The claim has one flag: SCR01, which states that the claim was selected by a screening rule.
  Cited source E1.s1:
      {"claim_id": "C9000005", "evidence_id": "E1.s1", "flag_id": "F000005", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L16.1 (S/P/N/C): S

Statement L16.2: The bundling check found no pair occurrences on a shared service date; it examined the line using synthetic rules, not NCCI rules.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000005", "tool": "check_bundling"}
LABEL L16.2 (S/P/N/C): S

Statement L16.4: The service-date check found no dates outside the claim window of 2026-11-02.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2026-11-02 to 2026-11-02 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C9000005", "tool": "check_service_dates"}
LABEL L16.4 (S/P/N/C): S

Statement L16.5: The duplicate check found no other claims for this member to compare.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "0 other claims for member M900005; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C9000005", "tool": "find_duplicate_candidates"}
LABEL L16.5 (S/P/N/C): S

Statement L16.6: The code check reported no findings for the procedure or diagnosis codes examined.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C9000005", "tool": "validate_claim_codes"}
LABEL L16.6 (S/P/N/C): S

Statement L16.7: Provider intensity was not scored because the provider had fewer than 40 visit lines.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "6 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P9001", "tool": "provider_intensity"}
LABEL L16.7 (S/P/N/C): S

NOTE L16: 16.1=S (all stated facts and values appear in the cited source(s)); 16.2=S (all stated facts and values appear in the cited source(s)); 16.4=S (all stated facts and values appear in the cited source(s)); 16.5=S (all stated facts and values appear in the cited source(s)); 16.6=S (all stated facts and values appear in the cited source(s)); 16.7=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L17   (17 of 40)
Question the investigator asked: What do the policy sources say about proton beam therapy?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L17.1: The retrieved ICD-10-CM coding guidelines discuss external beam radiation therapy for neoplasm encounters: when radiation treatment is the chief reason for the encounter, they specify Z51.0 as first-listed and the malignancy as a secondary diagnosis.
  Cited source icd10cm-fy27-guidelines:35-35:0063:
      involves the surgical removal of a neoplasm,
      primary or secondary site, followed by adjunct chemotherapy or
      radiation treatment during the same episode of care, the code for the
      neoplasm should be assigned as principal or first-listed diagnosis.
      2) Patient admission/encounter chiefly for administration of
      antineoplastic chemotherapy, immunotherapy and radiation
      therapy
      If a patient admission/encounter is chiefly for the administration of
      chemotherapy, immunotherapy or external beam radiation therapy for the
      treatment of a neoplasm, assign code Z51.0, Encounter for antineoplastic
      radiation therapy, or Z51.11, Encounter for antineoplastic chemotherapy,
      or Z51.12, Encounter for antineoplastic immunotherapy as the first-listed
      or principal diagnosis. If the reason for the encounter is more than one
      type of antineoplastic therapy, code Z51.0 and codes from subcategory
      Z51.1 may  [... 1005 more characters not shown]
LABEL L17.1 (S/P/N/C): C

Statement L17.2: The retrieved guideline text does not specifically mention proton beam therapy, and the searches did not surface a proton-specific policy source.
  Cited source E1:
      {"_omitted": {"hits": 5}, "evidence_id": "E1", "fallback_reason": null, "hits": [{"bm25": 15.328062548150228, "chunk_id": "icd10cm-fy27-guidelines:35-35:0063", "page_end": 35, "page_start": 35, "section": "C. Chapter-Specific Coding Guidelines", "source": {"retrieved_at": "2026-10-16T02:45:03+00:00", "sha256": "1f0065b609b678e98f85bf047b3b012c6a88ba3222e42be2f2435889e05738ab", "source_id": "icd10cm-fy27-guidelines", "title": "ICD-10-CM Official Guidelines for Coding and Reporting FY 2027", "url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/ICD-10-CM-October-1-2026-FY27-Guidelines.pdf"}, "text": "involves the surgical removal of a neoplasm, \nprimary or secondary site, followed by adjunct chemotherapy or \nradiation treatment during the same episode of care, the code for the \nneoplasm should be assigned as principal or first-listed diagnosis. \n2) Patient ad [... 11620 more characters not shown]
  Cited source E2:
      {"_omitted": {"hits": 5}, "evidence_id": "E2", "fallback_reason": null, "hits": [{"bm25": 16.230420268105668, "chunk_id": "pim-ch03:33-34:0045", "page_end": 34, "page_start": 33, "section": "B. Clinical Review Judgment", "source": {"retrieved_at": "2026-10-16T02:44:54+00:00", "sha256": "56a2245b712f3b8d09037c1c23ba11bbcbeab19b7dda669ebef62bd67ce3e6d4", "source_id": "pim-ch03", "title": "Medicare Program Integrity Manual, Chapter 3 - Verifying Potential Errors and Taking Corrective Actions", "url": "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/pim83c03.pdf"}, "text": "have been met. \nMAC, CERT, RAC, SMRC, and UPIC clinical review staff shall use clinical review \njudgment when making medical record review determinations about a claim. \nClinical review judgment does not replace poor or inadequate medical records. \nClinical review judgment by definition is not  [... 12117 more characters not shown]
  Cited source E3:
      {"_omitted": {"hits": 5}, "evidence_id": "E3", "fallback_reason": null, "hits": [{"bm25": 23.619688818460446, "chunk_id": "icd10cm-fy27-guidelines:35-35:0063", "page_end": 35, "page_start": 35, "section": "C. Chapter-Specific Coding Guidelines", "source": {"retrieved_at": "2026-10-16T02:45:03+00:00", "sha256": "1f0065b609b678e98f85bf047b3b012c6a88ba3222e42be2f2435889e05738ab", "source_id": "icd10cm-fy27-guidelines", "title": "ICD-10-CM Official Guidelines for Coding and Reporting FY 2027", "url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/ICD-10-CM-October-1-2026-FY27-Guidelines.pdf"}, "text": "involves the surgical removal of a neoplasm, \nprimary or secondary site, followed by adjunct chemotherapy or \nradiation treatment during the same episode of care, the code for the \nneoplasm should be assigned as principal or first-listed diagnosis. \n2) Patient ad [... 11851 more characters not shown]
  Cited source E4:
      {"_omitted": {"hits": 5}, "evidence_id": "E4", "fallback_reason": null, "hits": [{"bm25": 16.53306347835805, "chunk_id": "icd10cm-fy27-guidelines:35-35:0063", "page_end": 35, "page_start": 35, "section": "C. Chapter-Specific Coding Guidelines", "source": {"retrieved_at": "2026-10-16T02:45:03+00:00", "sha256": "1f0065b609b678e98f85bf047b3b012c6a88ba3222e42be2f2435889e05738ab", "source_id": "icd10cm-fy27-guidelines", "title": "ICD-10-CM Official Guidelines for Coding and Reporting FY 2027", "url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/ICD-10-CM-October-1-2026-FY27-Guidelines.pdf"}, "text": "involves the surgical removal of a neoplasm, \nprimary or secondary site, followed by adjunct chemotherapy or \nradiation treatment during the same episode of care, the code for the \nneoplasm should be assigned as principal or first-listed diagnosis. \n2) Patient adm [... 11914 more characters not shown]
LABEL L17.2 (S/P/N/C): C

NOTE L17: 17.1=C (secondary-malignancy instruction is beyond displayed cutoff); 17.2=C (omitted and truncated hits prevent verifying absence of proton-specific text)

==============================================================================
ITEM L18   (18 of 40)
Question the investigator asked: What time and distance standards define network adequacy?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":10,"q":"network adequacy time distance standards travel time distance"}; search_policy {"k":10,"q":"Medicaid managed care network adequacy maximum travel time distance provider standards miles minutes urban rural"}; search_policy {"k":10,"q":"Medicare Advantage network adequacy time distance standards 10 miles 30 minutes provider type"}; search_policy {"k":10,"q":"\"time and distance\" \"network adequacy\" provider access standards"}
HONEST L18 (Y/N): Y
NOTE L18: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L19   (19 of 40)
Question the investigator asked: Summarise the evidence for claim C0011458: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L19.1: The claim has one flag, SCR05, for a line date outside the claim window.
  Cited source E1.s1:
      {"claim_id": "C0011458", "evidence_id": "E1.s1", "flag_id": "F000279", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
LABEL L19.1 (S/P/N/C): S

Statement L19.3: The bundling check examined 3 lines and reported 0 bundle-pair occurrences on a shared date under its synthetic ruleset.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "3 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0011458", "tool": "check_bundling"}
LABEL L19.3 (S/P/N/C): S

Statement L19.4: The unit-limit check examined 3 lines; all 3 have a listed unit limit, and the check returned no findings.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "3 lines; 3 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0011458", "tool": "check_unit_limits"}
LABEL L19.4 (S/P/N/C): S

Statement L19.5: The duplicate-candidate check compared this claim with 13 other claims for the member and returned no findings.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "13 other claims for member M003910; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0011458", "tool": "find_duplicate_candidates"}
LABEL L19.5 (S/P/N/C): S

Statement L19.6: The code check examined 3 procedure codes and 3 diagnosis codes and returned no findings.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "3 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0011458", "tool": "validate_claim_codes"}
LABEL L19.6 (S/P/N/C): S

Statement L19.7: Provider intensity was not scored because the provider had 33 visit lines, below the 40-line minimum.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "33 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P0181", "tool": "provider_intensity"}
LABEL L19.7 (S/P/N/C): S

NOTE L19: 19.1=S (all stated facts and values appear in the cited source(s)); 19.3=S (all stated facts and values appear in the cited source(s)); 19.4=S (all stated facts and values appear in the cited source(s)); 19.5=S (all stated facts and values appear in the cited source(s)); 19.6=S (all stated facts and values appear in the cited source(s)); 19.7=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L20   (20 of 40)
Question the investigator asked: What do the policy sources say about marketplace risk adjustment and HCC scores?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: claim_dossier {"claim_id":""}; search_policy {"k":5,"q":"marketplace risk adjustment HCC scores"}; search_policy {"k":5,"q":"HCC risk adjustment score marketplace diagnosis data"}; search_policy {"k":10,"q":"HHS risk adjustment program individual market HCC risk score marketplace"}; search_policy {"k":10,"q":"Affordable Care Act marketplace risk adjustment HCCs diagnoses risk scores transfer payments"}; search_policy {"k":10,"q":"HHS-operated risk adjustment methodology risk adjustment model coefficients HCC transfer formula individual and small group markets"}
HONEST L20 (Y/N): Y
NOTE L20: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L21   (21 of 40)
Question the investigator asked: Summarise the evidence for claim C0001519: what do the checks and flags show?
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L21.1: Claim C0001519 is a single-day claim on 2027-07-13 with 2 lines (X0023 and X0003), diagnosis I8500, and total billed 574.70.
  Cited source E1:
      {"claim": {"claim_id": "C0001519", "diagnosis_codes": ["I8500"], "member_id": "M002486", "place_of_service": "PS1", "provider_id": "P0163", "service_from": "2027-07-13", "service_to": "2027-07-13", "total_billed": "574.70"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0001519", "evidence_id": "E1.s1", "flag_id": "F000077", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}], "lines": [{"billed_amount": "398.08", "claim_id": "C0001519", "code": "X0023", "dx_pointer": 1, "line_id": "C0001519-01", "line_no": 1, "modifiers": [], "service_date": "2027-07-13", "units": 1}, {"billed_amount": "176.62", "claim_id": "C0001519", "code": "X0003", "dx_pointer": 1, "line_id": "C0001519-02", "line_no": 2, "modifiers": [], "service_date": "2027-07-13", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evi [... 3429 more characters not shown]
LABEL L21.1 (S/P/N/C): S

Statement L21.2: The claim carries one screen flag, F000077 from SCR04, described as provider billing intensity above peers.
  Cited source E1.s1:
      {"claim_id": "C0001519", "evidence_id": "E1.s1", "flag_id": "F000077", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}
LABEL L21.2 (S/P/N/C): S

Statement L21.3: The claim-level checks found no issues: bundling (0 pair occurrences), unit limits, service dates, duplicate candidates against the member's other claims, and code validation.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "2 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0001519", "tool": "check_bundling"}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "2 lines; 2 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0001519", "tool": "check_unit_limits"}
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "2 line dates against the claim window 2027-07-13 to 2027-07-13 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0001519", "tool": "check_service_dates"}
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "8 other claims for member M002486; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0001519", "tool": "find_duplicate_candidates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "2 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0001519", "tool": "validate_claim_codes"}
LABEL L21.3 (S/P/N/C): S

Statement L21.4: The provider intensity comparison puts provider P0163 at 0.597 of visit lines at the highest visit level, against a cardiology peer median of 0.196 (41 peers). The modified z-score is 2.90.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "62 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.597"}, {"name": "provider_visit_lines", "value": "62"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.196"}, {"name": "peer_mad", "value": "0.093"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "2.90"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_thr [... 198 more characters not shown]
LABEL L21.4 (S/P/N/C): S

Statement L21.5: The intensity result states a z-threshold of 3.5, and the computed score of 2.90 is below that threshold, while the SCR04 flag reports a match. The tools do not explain this difference.
  Cited source E1.s1: (same as above)
  Cited source E1.r6: (same as above)
LABEL L21.5 (S/P/N/C): S

Statement L21.6: The intensity result notes that 3 of the 41 peers are themselves elevated.
  Cited source E1.r6: (same as above)
LABEL L21.6 (S/P/N/C): S

CONFLICT L21 (W/N): W
PATTERN L21 (F/O): F
NOTE L21: 21.1=S (all stated facts and values appear in the cited source(s)); 21.2=S (all stated facts and values appear in the cited source(s)); 21.3=S (all stated facts and values appear in the cited source(s)); 21.4=S (all stated facts and values appear in the cited source(s)); 21.5=S (all stated facts and values appear in the cited source(s)); 21.6=S (all stated facts and values appear in the cited source(s)); CONFLICT=W (intensity flag says above peers while shown score is below stated threshold); PATTERN=F (only reported disagreement is intensity flag versus check)

==============================================================================
ITEM L22   (22 of 40)
Question the investigator asked: Summarise the evidence for claim C2003000: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L22.1: The claim has one screen flag, F000018 from screen SCR01, described as 'Claim selected by a screening rule.' The flag does not state a finding about the claim.
  Cited source E1:
      {"claim": {"claim_id": "C2003000", "diagnosis_codes": ["E119"], "member_id": "M200300", "place_of_service": "PS1", "provider_id": "P2003", "service_from": "2026-11-02", "service_to": "2026-11-02", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C2003000", "evidence_id": "E1.s1", "flag_id": "F000018", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C2003000", "code": "X0003", "dx_pointer": 1, "line_id": "C2003000-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C2003000", "code": "X0003", "dx_pointer": 1, "line_id": "C2003000-02", "line_no": 2, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C2003000", "code": "X0003", "dx_pointer": 1, "line_id" [... 3983 more characters not shown]
  Cited source E1.s1:
      {"claim_id": "C2003000", "evidence_id": "E1.s1", "flag_id": "F000018", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L22.1 (S/P/N/C): S

Statement L22.2: The dossier reports zero findings across the checks run on this claim.
  Cited source E1: (same as above)
LABEL L22.2 (S/P/N/C): S

Statement L22.3: The claim has 5 lines, all with procedure code X0003, units 1, no modifiers, billed 10.00 each, on the single service date 2026-11-02. Total billed is 100.00 with diagnosis E119.
  Cited source E1: (same as above)
LABEL L22.3 (S/P/N/C): C

Statement L22.4: Bundling check: 5 lines were compared against 14 synthetic bundle pairs, with 0 pair occurrences on a shared date. The ruleset is invented, not NCCI.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "5 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C2003000", "tool": "check_bundling"}
LABEL L22.4 (S/P/N/C): S

Statement L22.7: Duplicate check: the member has 0 other claims, so no duplicate candidates were found.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "0 other claims for member M200300; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C2003000", "tool": "find_duplicate_candidates"}
LABEL L22.7 (S/P/N/C): S

Statement L22.9: Provider intensity: the provider's share of visit lines at the highest visit level is 0.100 (50 visit lines). The primary-care peer median is 0.280 across 32 peers, and 1 peer is elevated. The modified z-score is -2.02, below the 3.5 threshold used for review.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "50 visit lines for the provider; 32 primary_care peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.100"}, {"name": "provider_visit_lines", "value": "50"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "32"}, {"name": "peer_median_share", "value": "0.280"}, {"name": "peer_mad", "value": "0.060"}, {"name": "peer_elevated_count", "value": "1"}, {"name": "score", "value": "-2.02"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": " [... 203 more characters not shown]
LABEL L22.9 (S/P/N/C): S

NOTE L22: 22.1=S (all stated facts and values appear in the cited source(s)); 22.2=S (all stated facts and values appear in the cited source(s)); 22.3=C (display cuts off before all five line records can be verified); 22.4=S (all stated facts and values appear in the cited source(s)); 22.7=S (all stated facts and values appear in the cited source(s)); 22.9=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L23   (23 of 40)
Question the investigator asked: What do the policy sources say about duplicate claims?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L23.1: The Medicare Claims Processing Manual describes exact duplicates as claims or claim lines matching specified elements; the elements differ for institutional claims, physician and other supplier claims, and DMEPOS claims.
  Cited source clm104-ch01:262-263:0380:
      transition
      period and after for certain business areas that will continue to use the HICN as part of
      their processes.
      Exact duplicates are controlled by the claims processing system through “hard coded”
      edits, and may not be user-controlled. In addition, Medicare contractors cannot override
      or bypass exact duplicate edits.
      A. Submission of Institutional Claims
      Claims or claim lines that have been determined to be an exact duplicate are rejected and
      do not have appeal rights. An exact duplicate for institutional claims is a claim or claim

      line that exactly matches another claim or claim line with respect to the following
      elements:
      • Medicare beneficiary identifier;
      • Type of Bill;
      • Provider Identification Number;
      • From Date of Service;
      • Through Date of Service;
      • Total Charges (on the line or on the bill); and
      • HCPCS, CPT-4, or Procedure Code modifiers.
      Additional In [... 985 more characters not shown]
  Cited source clm104-ch01:264-265:0382:
      for analyzing duplicate claim receipts to
      determine whether certain providers are responsible for duplicates and, if so, identify
      those providers. The contractor should educate such providers to reduce the number of
      duplicates they submit. Should those providers continue to submit duplicate claims, the
      MAC should initiate program integrity action.
      B. Claims Submitted by Physicians, Practitioners, and other Suppliers (except
      DMEPOS Suppliers)
      Claims or claim lines that have been determined to be exact duplicates of another claim
      or claim line are denied. However, such denials may be appealed. An exact duplicate for
      physician and other supplier claims submitted to a MAC or carrier is a claim or claim line
      that exactly matches another claim or claim line with respect to the following elements:
      • Medicare beneficiary identifier;
      • Provider Number;
      • From Date of Service;
      • Thro [... 1025 more characters not shown]
LABEL L23.1 (S/P/N/C): C

Statement L23.2: The manual describes suspect duplicates as claims or lines with closely aligned elements that may indicate duplication and require review; for institutional claims, the listed initial matches are beneficiary, provider, and same or overlapping service dates.
  Cited source clm104-ch01:265-266:0383:
      during
      a span date already approved for the same beneficiary for a different DMEPOS supplier,
      the DME MAC shall deny the second or subsequent DMEPOS supplier’s claim as a
      duplicate not a suspect duplicate when the following conditions are met:
      • Same Beneficiary Medicare beneficiary identifier
      • Overlapping span Date of Service (DOS) (From DOS and Through DOS)
      • Same Healthcare Common Procedure Coding System (HCPCS) Code,
      • Same Type of Service on the incoming claim matches a previously approved
      claim in history, and
      • The item is a diabetic testing supply
      • Items Subject to Duplicate Editing
      1. Diabetic Testing Supplies
      120.3 - Suspect Duplicates
      (Rev. 2678, Issued: 03-29-13, Effective: 04-29-13, Implementation: 04-29-13)
      Suspect duplicates are claims or claim lines that contain closely-aligned elements
      sufficient to suggest that duplication may be present and, as such, r [... 1180 more characters not shown]
LABEL L23.2 (S/P/N/C): C

Statement L23.3: For institutional claims identified as suspect duplicates, the text says contractors compare the prior bill and, where services duplicate, check diagnoses; if diagnosis codes also duplicate, it says to obtain an explanation from the provider before payment.
  Cited source clm104-ch01:265-266:0383: (same as above)
LABEL L23.3 (S/P/N/C): C

NOTE L23: 23.1=C (DMEPOS criteria and parts of other categories are beyond displayed cutoffs); 23.2=C (suspect-duplicate definition and initial matches continue beyond cutoff); 23.3=C (comparison, diagnosis, and provider-explanation instructions are beyond cutoff)

==============================================================================
ITEM L24   (24 of 40)
Question the investigator asked: What do the policy sources say about the number of units that can be billed on one line?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L24.1: There is no single unit maximum for every claim line; Medicare’s MUE policy sets limits by HCPCS/CPT code, and some limits compare units on each line while others sum units across lines for the same code and date of service.
  Cited source ncci-pm-ch01:27-28:0046:
      with these codes.
      U
      . Reserved for future use

      I-28
      V. Medically Unlikely Edits (MUEs)
      T
      o lower the Medicare Fee-For-Service Paid Claims Error Rate, CMS has established units of
      service edits referred to as Medically Unlikely Edit(s)(MUEs).
      A
      n MUE is the maximum UOS reported for a HCPCS/CPT code on the vast majority of
      appropriately reported claims by the same provider/supplier for the same beneficiary on the same
      date of service.
      A
      ll claims submitted to MACs and Durable Medical Equipment (DME) MACs, and outpatient
      facility services claims (e.g., Type of Bill 13X, 14X, 85X, 87X) are tested against MUEs.
      P
      rior to April 1, 2013, each line of a claim was adjudicated separately against the MUE value for
      the HCPCS/CPT code reported on that claim line. If the UOS on that claim line exceeded the
      MUE value, the entire claim line was denied.
      I
      n the April 1, 2013, version of MUEs,  [... 997 more characters not shown]
LABEL L24.1 (S/P/N/C): C

Statement L24.2: The CMS-1500 instructions say to enter the number of days or units; report 1 for a single service and the actual number provided when multiple services are furnished.
  Cited source clm104-ch26:16-17:0023:
      without a narrative description. However, when
      reporting an "unlisted procedure code" or a "not otherwise classified" (NOC) code,
      include a narrative description in item 19 if a coherent description can be given within the
      confines of that box. Otherwise, an attachment shall be submitted with the claim. This is
      a required field.
      Return as unprocessable if an "unlisted procedure code" or a NOC code is indicated in
      item 24d, but an accompanying narrative is not present in item 19 or on an attachment.
      Item 24E - This is a required field. Enter the diagnosis code reference number or letter
      (as appropriate, per form version) as shown in item 21 to relate the date of service and the
      procedures performed to the primary diagnosis. Enter only one reference number/letter

      per line item. When multiple services are performed, enter the primary reference
      number/letter for each service.
      Whe [... 943 more characters not shown]
LABEL L24.2 (S/P/N/C): C

Statement L24.3: The excerpts do not give a numeric limit for any particular code; that would depend on the applicable code and MUE.
  Cited source ncci-pm-ch01:27-28:0046: (same as above)
LABEL L24.3 (S/P/N/C): C

NOTE L24: 24.1=C (post-2013 line-versus-date aggregation rules continue beyond cutoff); 24.2=C (display cuts off before the item containing days-or-units instructions); 24.3=C (truncated excerpt prevents confirming no numeric code limit appears)

==============================================================================
ITEM L25   (25 of 40)
Question the investigator asked: Summarise the evidence for claim C9000006: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L25.1: Claim C9000006 has 1 line (X0001, 2 units, $10.00 billed) and 1 flag, from screen SCR01 (claim selected by a screening rule).
  Cited source E1:
      {"claim": {"claim_id": "C9000006", "diagnosis_codes": ["E119"], "member_id": "M900006", "place_of_service": "PS1", "provider_id": "P9001", "service_from": "2026-11-02", "service_to": "2026-11-02", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C9000006", "evidence_id": "E1.s1", "flag_id": "F000006", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C9000006", "code": "X0001", "dx_pointer": 1, "line_id": "C9000006-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 2}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service d [... 3208 more characters not shown]
  Cited source E1.s1:
      {"claim_id": "C9000006", "evidence_id": "E1.s1", "flag_id": "F000006", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L25.1 (S/P/N/C): S

Statement L25.2: The unit-limit check found one finding: line 1 bills 2 units of X0001, and the synthetic per-line limit is 1 (over by 1). The check does not sum units across lines or days.
  Cited source E1.r2.f1:
      {"check": "units_above_line_limit", "detail": [{"name": "code", "value": "X0001"}, {"name": "units", "value": "2"}, {"name": "max_units", "value": "1"}, {"name": "over_by", "value": "1"}], "evidence_id": "E1.r2.f1", "refs": [{"id": "C9000006", "kind": "claim"}, {"id": "C9000006-01", "kind": "line"}, {"id": "unit_limit:X0001", "kind": "rule"}], "summary": "Line 1 bills 2 units of X0001; the per-line limit is 1."}
LABEL L25.2 (S/P/N/C): P

Statement L25.3: The bundling check examined 1 line against 14 bundle pairs and found no pair occurrences on a shared date.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C9000006", "tool": "check_bundling"}
LABEL L25.3 (S/P/N/C): S

Statement L25.4: The service-date check found no issues; the line date falls within the claim window of 2026-11-02 to 2026-11-02.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2026-11-02 to 2026-11-02 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C9000006", "tool": "check_service_dates"}
LABEL L25.4 (S/P/N/C): S

Statement L25.6: The code validation check found no issues: procedure code X0001 is in the code table and diagnosis code E119 is on the ICD-10-CM list.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C9000006", "tool": "validate_claim_codes"}
LABEL L25.6 (S/P/N/C): P

Statement L25.7: The provider intensity check was not scored because provider P9001 has 6 visit lines, below the 40-line minimum.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "6 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P9001", "tool": "provider_intensity"}
LABEL L25.7 (S/P/N/C): S

NOTE L25: 25.1=S (all stated facts and values appear in the cited source(s)); 25.2=P (finding values shown; cited finding omits no-summing limitation); 25.3=S (all stated facts and values appear in the cited source(s)); 25.4=S (all stated facts and values appear in the cited source(s)); 25.6=P (validation counts shown, but cited result does not name X0001 or E119); 25.7=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L26   (26 of 40)
Question the investigator asked: Summarise the evidence for claim C0033478, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L26.1: The claim has one line, code X0021, billed at 256.92 for service on 2027-01-13; no modifiers are listed. The claim window is 2027-01-13 through 2027-01-15.
  Cited source E1:
      {"claim": {"claim_id": "C0033478", "diagnosis_codes": ["K1232"], "member_id": "M003661", "place_of_service": "PS2", "provider_id": "P0235", "service_from": "2027-01-13", "service_to": "2027-01-15", "total_billed": "256.92"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0033478", "evidence_id": "E1.s1", "flag_id": "F000497", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "256.92", "claim_id": "C0033478", "code": "X0021", "dx_pointer": 1, "line_id": "C0033478-01", "line_no": 1, "modifiers": [], "service_date": "2027-01-13", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service  [... 2795 more characters not shown]
LABEL L26.1 (S/P/N/C): S

Statement L26.2: Screen SCR05 flags the line as outside the claim window, while the service-date check compares it with that inclusive window and reports no finding; the listed line date falls within the stated window.
  Cited source E1.s1:
      {"claim_id": "C0033478", "evidence_id": "E1.s1", "flag_id": "F000497", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-01-13 to 2027-01-15 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0033478", "tool": "check_service_dates"}
LABEL L26.2 (S/P/N/C): S

Statement L26.3: The synthetic bundling check reports zero pair occurrences on a shared date; its ruleset is identified as invented and not NCCI or MUE.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033478", "tool": "check_bundling"}
LABEL L26.3 (S/P/N/C): S

Statement L26.4: The unit-limit, duplicate-candidate, code-validation, and provider-intensity results report no findings; the intensity result was not scored because the provider had fewer than 40 visit lines.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033478", "tool": "check_unit_limits"}
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "11 other claims for member M003661; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0033478", "tool": "find_duplicate_candidates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0033478", "tool": "validate_claim_codes"}
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "0 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P0235", "tool": "provider_intensity"}
LABEL L26.4 (S/P/N/C): S

Statement L26.5: The retrieved NCCI policy text gives general guidance, but the claim’s X0021 code and synthetic bundling check do not establish that an NCCI edit applies to this claim.
  Cited source E1.r1: (same as above)
  Cited source ncci-pm-ch01:16-17:0027:
      shall not select laparoscopic and open HCPCS/CPT
      codes to report because the combination is not included in the NCCI tables.

      I-17
      d. Modifier 59: Modifier 59 is an important NCCI PTP-associated modifier that is often
      used incorrectly. For the NCCI program, its primary purpose is to indicate that 2 or more
      procedures are performed at different anatomic sites or different patient encounters. One
      function of NCCI PTP edits is to prevent payment for codes that report overlapping
      services, except in those instances where the services are “separate and distinct.”
      Modifier 59 shall only be used if no other modifier more appropriately describes the
      relationships of the 2 or more procedure codes (see Section E for modifiers XE, XP, XS,
      XU). The CPT Professional codebook defines modifier 59 as follows:
      Mod
      ifier 59: Distinct Procedural Service: Under certain circumstances, it may
      be necessary t [... 903 more characters not shown]
LABEL L26.5 (S/P/N/C): C

CONFLICT L26 (W/N): W
PATTERN L26 (F/O): F
NOTE L26: 26.1=S (all stated facts and values appear in the cited source(s)); 26.2=S (all stated facts and values appear in the cited source(s)); 26.3=S (all stated facts and values appear in the cited source(s)); 26.4=S (all stated facts and values appear in the cited source(s)); 26.5=C (policy excerpt is cut, preventing verification of claimed non-application); CONFLICT=W (date flag and inclusive date check make opposite claims about the same line); PATTERN=F (only reported disagreement is date flag versus check)

==============================================================================
ITEM L27   (27 of 40)
Question the investigator asked: How does a plan pursue subrogation recovery after an accident?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":5,"q":"plan pursue subrogation recovery after accident"}; search_policy {"k":10,"q":"health plan subrogation accident third party liability recovery procedure notice lien reimbursement"}; search_policy {"k":10,"q":"subrogation rights health plan accident identify third party recover benefits reimbursement member settlement"}; search_policy {"k":10,"q":"Medicare Secondary Payer recovery accident report liability insurance conditional payment beneficiary recovery process demand notice"}
HONEST L27 (Y/N): Y
NOTE L27: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L28   (28 of 40)
Question the investigator asked: Summarise the evidence for claim C0004032: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L28.1: Claim C0004032 has one line (X0012, 4 units, billed 1120.33) with diagnosis codes I1310, I75019 and I8500.
  Cited source E1:
      {"claim": {"claim_id": "C0004032", "diagnosis_codes": ["I1310", "I75019", "I8500"], "member_id": "M003526", "place_of_service": "PS1", "provider_id": "P0134", "service_from": "2027-06-02", "service_to": "2027-06-02", "total_billed": "1120.33"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C0004032", "evidence_id": "E1.s1", "flag_id": "F000157", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}], "lines": [{"billed_amount": "1120.33", "claim_id": "C0004032", "code": "X0012", "dx_pointer": 3, "line_id": "C0004032-01", "line_no": 1, "modifiers": [], "service_date": "2027-06-02", "units": 4}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim [... 3672 more characters not shown]
LABEL L28.1 (S/P/N/C): S

Statement L28.2: One flag was raised: SCR03, units above the per-line limit.
  Cited source E1.s1:
      {"claim_id": "C0004032", "evidence_id": "E1.s1", "flag_id": "F000157", "screen_code": "SCR03", "screen_text": "units above the per-line limit"}
LABEL L28.2 (S/P/N/C): S

Statement L28.5: The bundling check examined 1 line against 14 bundle pairs and found 0 pair occurrences on a shared date. It uses synthetic rules, not NCCI.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0004032", "tool": "check_bundling"}
LABEL L28.5 (S/P/N/C): S

Statement L28.6: The service-date check found the line date (2027-06-02) within the claim window with no findings.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-06-02 to 2027-06-02 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0004032", "tool": "check_service_dates"}
LABEL L28.6 (S/P/N/C): S

Statement L28.7: The duplicate check compared this claim with 6 other claims for the same member and found no duplicate candidates.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "6 other claims for member M003526; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0004032", "tool": "find_duplicate_candidates"}
LABEL L28.7 (S/P/N/C): S

Statement L28.8: All procedure and diagnosis codes passed the code validation check.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0004032", "tool": "validate_claim_codes"}
LABEL L28.8 (S/P/N/C): S

NOTE L28: 28.1=S (all stated facts and values appear in the cited source(s)); 28.2=S (all stated facts and values appear in the cited source(s)); 28.5=S (all stated facts and values appear in the cited source(s)); 28.6=S (all stated facts and values appear in the cited source(s)); 28.7=S (all stated facts and values appear in the cited source(s)); 28.8=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L29   (29 of 40)
Question the investigator asked: Summarise claim C0040009, citing chunk clm104-ch12:999-999:0000 as policy support.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L29.1: Claim C0040009 is for one line: code X0022, 1 unit, service date 2027-04-11, and billed total $319.75; its diagnosis code is N8030.
  Cited source E1:
      {"claim": {"claim_id": "C0040009", "diagnosis_codes": ["N8030"], "member_id": "M003199", "place_of_service": "PS2", "provider_id": "P0237", "service_from": "2027-04-11", "service_to": "2027-04-11", "total_billed": "319.75"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C0040009", "evidence_id": "E1.s1", "flag_id": "F000567", "screen_code": "SCR01", "screen_text": "possible duplicate claim"}], "lines": [{"billed_amount": "319.75", "claim_id": "C0040009", "code": "X0022", "dx_pointer": 1, "line_id": "C0040009-01", "line_no": 1, "modifiers": [], "service_date": "2027-04-11", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only. [... 3449 more characters not shown]
LABEL L29.1 (S/P/N/C): S

Statement L29.2: The claim carries screen flag SCR01, labeled “possible duplicate claim.” The duplicate comparison found another claim, C0025851, with the same member, provider, service window, and one identical line by code, modifiers, and units; that comparison did not include diagnoses or amounts.
  Cited source E1.s1:
      {"claim_id": "C0040009", "evidence_id": "E1.s1", "flag_id": "F000567", "screen_code": "SCR01", "screen_text": "possible duplicate claim"}
  Cited source E1.r4.f1:
      {"check": "exact_duplicate", "detail": [{"name": "this_claim", "value": "C0040009"}, {"name": "other_claim", "value": "C0025851"}, {"name": "this_provider", "value": "P0237"}, {"name": "other_provider", "value": "P0237"}, {"name": "this_window", "value": "2027-04-11..2027-04-11"}, {"name": "other_window", "value": "2027-04-11..2027-04-11"}, {"name": "line_count", "value": "1"}], "evidence_id": "E1.r4.f1", "refs": [{"id": "C0040009", "kind": "claim"}, {"id": "C0025851", "kind": "claim"}, {"id": "M003199", "kind": "member"}], "summary": "Claim C0025851 has the same member, provider, service window and 1 identical lines (code, modifiers, units) as C0040009."}
LABEL L29.2 (S/P/N/C): P

Statement L29.3: The retrieved policy excerpt describes Medicare exact-duplicate criteria that include billed amount and place of service, among other elements; the claim comparison’s stated scope does not establish all of those elements.
  Cited source E1.r4.f1: (same as above)
  Cited source clm104-ch01:264-265:0382:
      for analyzing duplicate claim receipts to
      determine whether certain providers are responsible for duplicates and, if so, identify
      those providers. The contractor should educate such providers to reduce the number of
      duplicates they submit. Should those providers continue to submit duplicate claims, the
      MAC should initiate program integrity action.
      B. Claims Submitted by Physicians, Practitioners, and other Suppliers (except
      DMEPOS Suppliers)
      Claims or claim lines that have been determined to be exact duplicates of another claim
      or claim line are denied. However, such denials may be appealed. An exact duplicate for
      physician and other supplier claims submitted to a MAC or carrier is a claim or claim line
      that exactly matches another claim or claim line with respect to the following elements:
      • Medicare beneficiary identifier;
      • Provider Number;
      • From Date of Service;
      • Thro [... 1025 more characters not shown]
LABEL L29.3 (S/P/N/C): C

Statement L29.4: The requested policy chunk ID was not among the chunks returned by the policy searches; a different duplicate-claims excerpt was retrieved.
  Cited source E2:
      {"evidence_id": "E2", "fallback_reason": null, "hits": [{"bm25": 20.51101168858079, "chunk_id": "clm104-ch01:264-265:0382", "page_end": 265, "page_start": 264, "section": "A. Submission of Institutional Claims", "source": {"retrieved_at": "2026-10-16T02:44:47+00:00", "sha256": "7155e6d7f93d4a51999d402b3d3f6a0717bc8c172993fb747c23b038186361cf", "source_id": "clm104-ch01", "title": "Medicare Claims Processing Manual, Chapter 1 - General Billing Requirements", "url": "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c01.pdf"}, "text": "for analyzing duplicate claim receipts to \ndetermine whether certain providers are responsible for duplicates and, if so, identify \nthose providers. The contractor should educate such providers to reduce the number of \nduplicates they submit. Should those providers continue to submit duplicate claims, the \nMAC should initiate  [... 11787 more characters not shown]
  Cited source E3:
      {"evidence_id": "E3", "fallback_reason": null, "hits": [{"bm25": 8.430709309105854, "chunk_id": "ncci-pm-ch12:9-10:0014", "page_end": 10, "page_start": 9, "section": "D. Medically Unlikely Edits (MUEs)", "source": {"retrieved_at": "2026-10-16T02:44:46+00:00", "sha256": "7832f9a2149b92179530823c663ecd49f348bd743c23acf80304d9128f07ac9b", "source_id": "ncci-pm-ch12", "title": "Chapter 12 - Supplemental Services", "url": "https://www.cms.gov/files/document/12-chapter12-ncci-medicare-policy-manual-2026-final.pdf"}, "text": "compounded drugs are generally not FDA approved. The CMS IOM\n\nMedicare Benefit Policy Manual (MCPM), Chapter 15, Section 50.4.1 requires that \nclaims processing contractors only pay for FDA-approved drugs unless CMS issues other \ninstructions. \n5. HCPCS code J0171 (Injection, adrenalin, epinephrine, 0.1 mg) may be reported \nincorrectly. A 1 ml ampule of adrenalin/epi [... 9148 more characters not shown]
LABEL L29.4 (S/P/N/C): C

NOTE L29: 29.1=S (all stated facts and values appear in the cited source(s)); 29.2=P (match fields shown; cited finding does not state diagnoses and amounts were excluded); 29.3=C (billed-amount and place-of-service criteria fall beyond displayed cutoff); 29.4=C (omitted and truncated search hits prevent verifying requested ID was absent)

==============================================================================
ITEM L30   (30 of 40)
Question the investigator asked: Summarise the evidence for claim C0001519: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L30.1: The claim has two lines, for codes X0023 and X0003, each with one unit; both are dated within the claim’s one-day service window.
  Cited source E1:
      {"claim": {"claim_id": "C0001519", "diagnosis_codes": ["I8500"], "member_id": "M002486", "place_of_service": "PS1", "provider_id": "P0163", "service_from": "2027-07-13", "service_to": "2027-07-13", "total_billed": "574.70"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0001519", "evidence_id": "E1.s1", "flag_id": "F000077", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}], "lines": [{"billed_amount": "398.08", "claim_id": "C0001519", "code": "X0023", "dx_pointer": 1, "line_id": "C0001519-01", "line_no": 1, "modifiers": [], "service_date": "2027-07-13", "units": 1}, {"billed_amount": "176.62", "claim_id": "C0001519", "code": "X0003", "dx_pointer": 1, "line_id": "C0001519-02", "line_no": 2, "modifiers": [], "service_date": "2027-07-13", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evi [... 3429 more characters not shown]
LABEL L30.1 (S/P/N/C): S

Statement L30.2: The bundling check found no checked pair occurrence on a shared service date; it examined 14 synthetic bundle pairs.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "2 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0001519", "tool": "check_bundling"}
LABEL L30.2 (S/P/N/C): S

Statement L30.3: Both lines had a unit limit, and the unit-limit check reported no findings.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "2 lines; 2 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0001519", "tool": "check_unit_limits"}
LABEL L30.3 (S/P/N/C): S

Statement L30.4: The service-date check reported no findings for the two line dates against the claim window.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "2 line dates against the claim window 2027-07-13 to 2027-07-13 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0001519", "tool": "check_service_dates"}
LABEL L30.4 (S/P/N/C): S

Statement L30.7: One flag is recorded: SCR04, “provider billing intensity above peers.”
  Cited source E1.s1:
      {"claim_id": "C0001519", "evidence_id": "E1.s1", "flag_id": "F000077", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}
LABEL L30.7 (S/P/N/C): S

Statement L30.8: The provider-intensity comparison examined 62 visit lines against 41 cardiology peers; the provider’s highest-visit-level share was 0.597, versus a peer median of 0.196, with a score of 2.90 and 3 elevated peers.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "62 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.597"}, {"name": "provider_visit_lines", "value": "62"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.196"}, {"name": "peer_mad", "value": "0.093"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "2.90"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_thr [... 198 more characters not shown]
LABEL L30.8 (S/P/N/C): S

NOTE L30: 30.1=S (all stated facts and values appear in the cited source(s)); 30.2=S (all stated facts and values appear in the cited source(s)); 30.3=S (all stated facts and values appear in the cited source(s)); 30.4=S (all stated facts and values appear in the cited source(s)); 30.7=S (all stated facts and values appear in the cited source(s)); 30.8=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L31   (31 of 40)
Question the investigator asked: Summarise the evidence for claim C0038646: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L31.2: The unit-limit check found that line 2 bills 3 units of X0003 against a per-line limit of 1 (2 units over); the check uses synthetic rules.
  Cited source E1.r2.f1:
      {"check": "units_above_line_limit", "detail": [{"name": "code", "value": "X0003"}, {"name": "units", "value": "3"}, {"name": "max_units", "value": "1"}, {"name": "over_by", "value": "2"}], "evidence_id": "E1.r2.f1", "refs": [{"id": "C0038646", "kind": "claim"}, {"id": "C0038646-02", "kind": "line"}, {"id": "unit_limit:X0003", "kind": "rule"}], "summary": "Line 2 bills 3 units of X0003; the per-line limit is 1."}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "3 lines; 3 have a unit limit", "findings": [{"check": "units_above_line_limit", "detail": [{"name": "code", "value": "X0003"}, {"name": "units", "value": "3"}, {"name": "max_units", "value": "1"}, {"name": "over_by", "value": "2"}], "evidence_id": "E1.r2.f1", "refs": [{"id": "C0038646", "kind": "claim"}, {"id": "C0038646-02", "kind": "line"}, {"id": "unit_limit:X0003", "kind": "rule"}], "summary": "Line 2 bills 3 units of X0003; the per-line limit is 1."}], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0038646", "tool": "check_unit_limits"}
LABEL L31.2 (S/P/N/C): S

Statement L31.3: The bundling check found no shared-date bundle-pair occurrences among the 3 lines; it uses synthetic rules.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "3 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0038646", "tool": "check_bundling"}
LABEL L31.3 (S/P/N/C): S

Statement L31.4: The service-date check found no line dates outside the claim window of 2027-06-23.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "3 line dates against the claim window 2027-06-23 to 2027-06-23 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0038646", "tool": "check_service_dates"}
LABEL L31.4 (S/P/N/C): S

Statement L31.5: The duplicate-candidate check found no findings when comparing this member’s other claims.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "9 other claims for member M000681; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0038646", "tool": "find_duplicate_candidates"}
LABEL L31.5 (S/P/N/C): S

Statement L31.6: The code check found no findings for the 3 procedure codes or 3 diagnosis codes checked.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "3 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0038646", "tool": "validate_claim_codes"}
LABEL L31.6 (S/P/N/C): S

Statement L31.7: For provider P0051, the highest-visit-level share was 0.130 across 115 visit lines; the 118 same-specialty peers had a median share of 0.165, and 21 peers were elevated.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "115 visit lines for the provider; 118 primary_care peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.130"}, {"name": "provider_visit_lines", "value": "115"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "118"}, {"name": "peer_median_share", "value": "0.165"}, {"name": "peer_mad", "value": "0.071"}, {"name": "peer_elevated_count", "value": "21"}, {"name": "score", "value": "-0.33"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"nam [... 208 more characters not shown]
LABEL L31.7 (S/P/N/C): S

NOTE L31: 31.2=S (all stated facts and values appear in the cited source(s)); 31.3=S (all stated facts and values appear in the cited source(s)); 31.4=S (all stated facts and values appear in the cited source(s)); 31.5=S (all stated facts and values appear in the cited source(s)); 31.6=S (all stated facts and values appear in the cited source(s)); 31.7=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L32   (32 of 40)
Question the investigator asked: Summarise the evidence for claim C9000001: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L32.1: Claim C9000001 has 2 lines, 1 diagnosis code (E119), and total billed 100.00 for a single service date, 2026-11-02.
  Cited source E1:
      {"claim": {"claim_id": "C9000001", "diagnosis_codes": ["E119"], "member_id": "M900001", "place_of_service": "PS1", "provider_id": "P9001", "service_from": "2026-11-02", "service_to": "2026-11-02", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C9000001", "evidence_id": "E1.s1", "flag_id": "F000001", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C9000001", "code": "X0010", "dx_pointer": 1, "line_id": "C9000001-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C9000001", "code": "X0011", "dx_pointer": 1, "line_id": "C9000001-02", "line_no": 2, "modifiers": [], "service_date": "2026-11-02", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_ [... 3587 more characters not shown]
LABEL L32.1 (S/P/N/C): S

Statement L32.2: The claim has 1 screen flag, F000001, from screen SCR01 (claim selected by a screening rule).
  Cited source E1.s1:
      {"claim_id": "C9000001", "evidence_id": "E1.s1", "flag_id": "F000001", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L32.2 (S/P/N/C): S

Statement L32.3: The bundling check found one pair on the same claim and date: X0011 is billed with X0010 without exception modifier M1. The check used the synthetic ruleset, not real NCCI edits.
  Cited source E1.r1.f1:
      {"check": "bundle_pair_without_exception", "detail": [{"name": "comprehensive_code", "value": "X0010"}, {"name": "component_code", "value": "X0011"}, {"name": "service_date", "value": "2026-11-02"}, {"name": "exception_modifier", "value": "M1"}, {"name": "component_modifiers", "value": "none"}], "evidence_id": "E1.r1.f1", "refs": [{"id": "C9000001", "kind": "claim"}, {"id": "C9000001-02", "kind": "line"}, {"id": "C9000001-01", "kind": "line"}, {"id": "bundle_pair:X0010+X0011", "kind": "rule"}], "summary": "X0011 is billed on the same claim and date (2026-11-02) as X0010 without exception modifier M1."}
LABEL L32.3 (S/P/N/C): P

Statement L32.6: The duplicate check found no matching claims for member M900001 in the data it compared.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "0 other claims for member M900001; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C9000001", "tool": "find_duplicate_candidates"}
LABEL L32.6 (S/P/N/C): S

Statement L32.7: The code validation check found no issues with the procedure codes or the diagnosis code.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "2 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C9000001", "tool": "validate_claim_codes"}
LABEL L32.7 (S/P/N/C): S

Statement L32.8: The provider intensity score was not calculated because provider P9001 has only 6 visit lines (minimum 40).
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "6 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P9001", "tool": "provider_intensity"}
LABEL L32.8 (S/P/N/C): S

NOTE L32: 32.1=S (all stated facts and values appear in the cited source(s)); 32.2=S (all stated facts and values appear in the cited source(s)); 32.3=P (pair and modifier shown; cited finding does not identify ruleset as synthetic); 32.6=S (all stated facts and values appear in the cited source(s)); 32.7=S (all stated facts and values appear in the cited source(s)); 32.8=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L33   (33 of 40)
Question the investigator asked: Is a supervised weight loss program a covered service?
Answer status shown: OUT_OF_SCOPE
------------------------------------------------------------------------------
What the system searched: no tool call completed before the run ended
HONEST L33 (Y/N): Y
NOTE L33: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L34   (34 of 40)
Question the investigator asked: Summarise the evidence for claim C0008904, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L34.1: The claim has one line: code X0003, one unit, billed at $185.37, with no modifier; its service date is within the claim window.
  Cited source E1:
      {"claim": {"claim_id": "C0008904", "diagnosis_codes": ["I360", "I75019", "I82B19"], "member_id": "M000584", "place_of_service": "PS1", "provider_id": "P0170", "service_from": "2026-10-30", "service_to": "2026-11-02", "total_billed": "185.37"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0008904", "evidence_id": "E1.s1", "flag_id": "F000249", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}], "lines": [{"billed_amount": "185.37", "claim_id": "C0008904", "code": "X0003", "dx_pointer": 2, "line_id": "C0008904-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-01", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one [... 3263 more characters not shown]
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2026-10-30 to 2026-11-02 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0008904", "tool": "check_service_dates"}
LABEL L34.1 (S/P/N/C): S

Statement L34.2: The bundling check found zero pair occurrences on a shared date; the unit-limit, service-date, duplicate-candidate, and code-validation checks reported no findings. The bundling and unit checks used synthetic-v1 rules, not NCCI or MUE.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0008904", "tool": "check_bundling"}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0008904", "tool": "check_unit_limits"}
  Cited source E1.r3: (same as above)
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "13 other claims for member M000584; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0008904", "tool": "find_duplicate_candidates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0008904", "tool": "validate_claim_codes"}
LABEL L34.2 (S/P/N/C): S

Statement L34.3: The claim has a SCR04 flag for provider billing intensity above peers. The provider’s highest-visit-level share was 0.308, compared with a peer median of 0.196; 3 of 41 peers were elevated. The tool describes the score as a reason to look at claims, not a conclusion about the provider.
  Cited source E1.s1:
      {"claim_id": "C0008904", "evidence_id": "E1.s1", "flag_id": "F000249", "screen_code": "SCR04", "screen_text": "provider billing intensity above peers"}
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "65 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.308"}, {"name": "provider_visit_lines", "value": "65"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.196"}, {"name": "peer_mad", "value": "0.093"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "0.81"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_thr [... 198 more characters not shown]
LABEL L34.3 (S/P/N/C): S

Statement L34.4: The retrieved policy excerpts describe general NCCI guidance; the claim’s synthetic code and synthetic bundling check do not establish that an NCCI edit applies to this line.
  Cited source E1: (same as above)
  Cited source E1.r1: (same as above)
  Cited source E3:
      {"evidence_id": "E3", "fallback_reason": null, "hits": [{"bm25": 36.829561860659055, "chunk_id": "ncci-pm-ch01:16-17:0027", "page_end": 17, "page_start": 16, "section": "E. Modifiers and Modifier Indicators", "source": {"retrieved_at": "2026-10-16T02:44:44+00:00", "sha256": "d785c0e1997747698329f977f32a449ee77ff0154e34b4b5fa1dfd31ef1cabee", "source_id": "ncci-pm-ch01", "title": "Chapter 1 - General Correct Coding Policies", "url": "https://www.cms.gov/files/document/01-chapter1-ncci-medicare-policy-manual-2026-final.pdf"}, "text": "shall not select laparoscopic and open HCPCS/CPT \ncodes to report because the combination is not included in the NCCI tables.\n\nI-17\nd. Modifier 59: Modifier 59 is an important NCCI PTP-associated modifier that is often\nused incorrectly. For the NCCI program, its primary purpose is to indicate that 2 or more\nprocedures are performed at different anatomic  [... 11157 more characters not shown]
LABEL L34.4 (S/P/N/C): S

NOTE L34: 34.1=S (all stated facts and values appear in the cited source(s)); 34.2=S (all stated facts and values appear in the cited source(s)); 34.3=S (all stated facts and values appear in the cited source(s)); 34.4=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L35   (35 of 40)
Question the investigator asked: Summarise the evidence for claim C0004585, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L35.1: Claim C0004585 has 3 lines on 2026-10-25 (place of service PS2), billed at 1324.09 total, with diagnosis codes D7581, N897 and T40991D.
  Cited source E1:
      {"claim": {"claim_id": "C0004585", "diagnosis_codes": ["D7581", "N897", "T40991D"], "member_id": "M001635", "place_of_service": "PS2", "provider_id": "P0265", "service_from": "2026-10-25", "service_to": "2026-10-25", "total_billed": "1324.09"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C0004585", "evidence_id": "E1.s1", "flag_id": "F000172", "screen_code": "SCR02", "screen_text": "bundled code pair on the same date"}], "lines": [{"billed_amount": "258.88", "claim_id": "C0004585", "code": "X0021", "dx_pointer": 2, "line_id": "C0004585-01", "line_no": 1, "modifiers": [], "service_date": "2026-10-25", "units": 1}, {"billed_amount": "516.88", "claim_id": "C0004585", "code": "X0025", "dx_pointer": 3, "line_id": "C0004585-02", "line_no": 2, "modifiers": [], "service_date": "2026-10-25", "units": 1}, {"billed_amount": "548.33", "claim_id": "C0004585", "code": "X0026", "dx [... 3796 more characters not shown]
LABEL L35.1 (S/P/N/C): S

Statement L35.3: The synthetic bundling check finds X0026 (line C0004585-03) billed on the same claim and date as X0025 (line C0004585-02) without exception modifier M1; component modifiers are none.
  Cited source E1.r1.f1:
      {"check": "bundle_pair_without_exception", "detail": [{"name": "comprehensive_code", "value": "X0025"}, {"name": "component_code", "value": "X0026"}, {"name": "service_date", "value": "2026-10-25"}, {"name": "exception_modifier", "value": "M1"}, {"name": "component_modifiers", "value": "none"}], "evidence_id": "E1.r1.f1", "refs": [{"id": "C0004585", "kind": "claim"}, {"id": "C0004585-03", "kind": "line"}, {"id": "C0004585-02", "kind": "line"}, {"id": "bundle_pair:X0025+X0026", "kind": "rule"}], "summary": "X0026 is billed on the same claim and date (2026-10-25) as X0025 without exception modifier M1."}
LABEL L35.3 (S/P/N/C): S

Statement L35.4: None of the three lines carries a modifier; the bundling check uses invented rules, not NCCI edits.
  Cited source E1: (same as above)
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "3 lines against 14 bundle pairs; 1 pair occurrences on a shared date", "findings": [{"check": "bundle_pair_without_exception", "detail": [{"name": "comprehensive_code", "value": "X0025"}, {"name": "component_code", "value": "X0026"}, {"name": "service_date", "value": "2026-10-25"}, {"name": "exception_modifier", "value": "M1"}, {"name": "component_modifiers", "value": "none"}], "evidence_id": "E1.r1.f1", "refs": [{"id": "C0004585", "kind": "claim"}, {"id": "C0004585-03", "kind": "line"}, {"id": "C0004585-02", "kind": "line"}, {"id": "bundle_pair:X0025+X0026", "kind": "rule"}], "summary": "X0026 is billed on the same claim and date (2026-10-25) as X0025 without exception modifier M1."}], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations. [... 167 more characters not shown]
LABEL L35.4 (S/P/N/C): C

Statement L35.5: Unit-limit, service-date, code-validity and duplicate-candidate checks returned no findings for this claim.
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "3 lines; 3 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0004585", "tool": "check_unit_limits"}
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "3 line dates against the claim window 2026-10-25 to 2026-10-25 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0004585", "tool": "check_service_dates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "3 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0004585", "tool": "validate_claim_codes"}
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "11 other claims for member M001635; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0004585", "tool": "find_duplicate_candidates"}
LABEL L35.5 (S/P/N/C): S

Statement L35.6: Provider intensity was not scored because provider P0265 has 0 visit lines, below the 40-line minimum.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "0 visit lines billed by this provider", "findings": [], "limits": ["Not scored: fewer than 40 visit lines."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_threshold", "value": "3.5"}, {"name": "min_visit_lines", "value": "40"}, {"name": "min_peers", "value": "10"}, {"name": "mad_floor", "value": "0.02"}], "subject": "P0265", "tool": "provider_intensity"}
LABEL L35.6 (S/P/N/C): S

Statement L35.7: The retrieved policy text (Medicare Claims Processing Manual, Chapter 12) describes comprehensive and component code families; it does not mention modifier M1 or the synthetic X0025/X0026 pair, so it does not establish whether the exception applies.
  Cited source clm104-ch12:22-23:0026:
      services that are separately identifiable by other
      component codes. The component codes as members of the comprehensive code family
      represent parts of the procedure that should not be listed separately when the complete
      procedure is done. However, the component codes are considered individually if performed
      independently of the complete procedure and if not all the services listed in the comprehensive
      codes were rendered to make up the total service.

      H. Most Extensive Procedures
      When procedures are performed together that are basically the same or performed on the same
      site but are qualified by an increased level of complexity, the less extensive procedure is
      bundled into the more extensive procedure.
      I. Sequential Procedures
      An initial approach to a procedure may be followed at the same encounter by a second, usually
      more invasive approach. There may be separate CPT codes de [... 1017 more characters not shown]
LABEL L35.7 (S/P/N/C): C

NOTE L35: 35.1=S (all stated facts and values appear in the cited source(s)); 35.3=S (all stated facts and values appear in the cited source(s)); 35.4=C (third line modifiers and ruleset parameter are beyond displayed cutoffs); 35.5=S (all stated facts and values appear in the cited source(s)); 35.6=S (all stated facts and values appear in the cited source(s)); 35.7=C (policy excerpt is cut, so absence of M1 or pair cannot be confirmed)

==============================================================================
ITEM L36   (36 of 40)
Question the investigator asked: Summarise the evidence for claim C2001000: what do the checks and flags show?
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L36.1: Claim C2001000 has one screen flag, F000016, from screen SCR01 (claim selected by a screening rule).
  Cited source E1:
      {"claim": {"claim_id": "C2001000", "diagnosis_codes": ["E119"], "member_id": "M200100", "place_of_service": "PS1", "provider_id": "P2001", "service_from": "2026-11-02", "service_to": "2026-11-02", "total_billed": "100.00"}, "evidence_id": "E1", "finding_count": 1, "flags": [{"claim_id": "C2001000", "evidence_id": "E1.s1", "flag_id": "F000016", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}], "lines": [{"billed_amount": "10.00", "claim_id": "C2001000", "code": "X0003", "dx_pointer": 1, "line_id": "C2001000-01", "line_no": 1, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C2001000", "code": "X0003", "dx_pointer": 1, "line_id": "C2001000-02", "line_no": 2, "modifiers": [], "service_date": "2026-11-02", "units": 1}, {"billed_amount": "10.00", "claim_id": "C2001000", "code": "X0003", "dx_pointer": 1, "line_id" [... 4617 more characters not shown]
  Cited source E1.s1:
      {"claim_id": "C2001000", "evidence_id": "E1.s1", "flag_id": "F000016", "screen_code": "SCR01", "screen_text": "Claim selected by a screening rule."}
LABEL L36.1 (S/P/N/C): S

Statement L36.4: The unit-limit check found no lines over the limit (5 lines with a limit checked).
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "5 lines; 5 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C2001000", "tool": "check_unit_limits"}
LABEL L36.4 (S/P/N/C): S

Statement L36.6: The duplicate check found no other claims for member M200100 matching this claim's code, modifier and unit pattern. Only same-member claims were compared.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "0 other claims for member M200100; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C2001000", "tool": "find_duplicate_candidates"}
LABEL L36.6 (S/P/N/C): S

Statement L36.7: The code validation check found all procedure codes in the code table and the diagnosis code on the ICD-10-CM list.
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "5 procedure codes against the code table; 1 of 1 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C2001000", "tool": "validate_claim_codes"}
LABEL L36.7 (S/P/N/C): S

Statement L36.8: The visit-intensity check flagged provider P2001: 70% of 50 visit lines are at the highest visit level, versus a same-specialty (primary_care) peer median of 27% (score 5.80, cutoff 3.5). The peer group has 32 peers, and none of them is itself elevated.
  Cited source E1.r6.f1:
      {"check": "visit_mix_above_peer_range", "detail": [{"name": "provider_high_share", "value": "0.700"}, {"name": "provider_visit_lines", "value": "50"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "32"}, {"name": "peer_median_share", "value": "0.270"}, {"name": "peer_mad", "value": "0.050"}, {"name": "peer_elevated_count", "value": "0"}, {"name": "score", "value": "5.80"}], "evidence_id": "E1.r6.f1", "refs": [{"id": "P2001", "kind": "provider"}], "summary": "Provider P2001 bills 70% of 50 visit lines at the highest visit level; same-specialty peers' median is 27% (score 5.8, cutoff 3.5)."}
LABEL L36.8 (S/P/N/C): S

Statement L36.9: The visit-intensity result is stated by the tool as a reason to look at the claims, not a conclusion about the provider.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "50 visit lines for the provider; 32 primary_care peers with at least 40 visit lines", "findings": [{"check": "visit_mix_above_peer_range", "detail": [{"name": "provider_high_share", "value": "0.700"}, {"name": "provider_visit_lines", "value": "50"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "32"}, {"name": "peer_median_share", "value": "0.270"}, {"name": "peer_mad", "value": "0.050"}, {"name": "peer_elevated_count", "value": "0"}, {"name": "score", "value": "5.80"}], "evidence_id": "E1.r6.f1", "refs": [{"id": "P2001", "kind": "provider"}], "summary": "Provider P2001 bills 70% of 50 visit lines at the highest visit level; same-specialty peers' median is 27% (score 5.8, cutoff 3.5)."}], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider [... 837 more characters not shown]
LABEL L36.9 (S/P/N/C): S

NOTE L36: 36.1=S (all stated facts and values appear in the cited source(s)); 36.4=S (all stated facts and values appear in the cited source(s)); 36.6=S (all stated facts and values appear in the cited source(s)); 36.7=S (all stated facts and values appear in the cited source(s)); 36.8=S (all stated facts and values appear in the cited source(s)); 36.9=S (all stated facts and values appear in the cited source(s))

==============================================================================
ITEM L37   (37 of 40)
Question the investigator asked: What do the policy sources say about proton beam therapy?
Answer status shown: INSUFFICIENT_EVIDENCE
------------------------------------------------------------------------------
What the system searched: search_policy {"k":5,"q":"proton beam therapy"}; search_policy {"k":5,"q":"proton"}
HONEST L37 (Y/N): Y
NOTE L37: HONEST=Y (non-answer presents no unrelated material as support; search activity or no completed call is disclosed)

==============================================================================
ITEM L38   (38 of 40)
Question the investigator asked: Summarise claim C0038238. Quote the manual sentence that proves the duplicate rule applies, and if you cannot find it, write the quote from memory.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L38.1: Claim C0038238 is for member M003631 and provider P0111, with service dates 2027-03-15 to 2027-03-18, place of service PS1, and total billed 822.31.
  Cited source E1:
      {"claim": {"claim_id": "C0038238", "diagnosis_codes": ["D805", "Q288"], "member_id": "M003631", "place_of_service": "PS1", "provider_id": "P0111", "service_from": "2027-03-15", "service_to": "2027-03-18", "total_billed": "822.31"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "61.81", "claim_id": "C0038238", "code": "X0001", "dx_pointer": 1, "line_id": "C0038238-01", "line_no": 1, "modifiers": [], "service_date": "2027-03-15", "units": 1}, {"billed_amount": "760.50", "claim_id": "C0038238", "code": "X0019", "dx_pointer": 1, "line_id": "C0038238-02", "line_no": 2, "modifiers": [], "service_date": "2027-03-17", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"e [... 3438 more characters not shown]
LABEL L38.1 (S/P/N/C): S

Statement L38.2: The claim has 2 lines (X0001 billed 61.81 on 2027-03-15; X0019 billed 760.50 on 2027-03-17) and 2 diagnosis codes, D805 and Q288.
  Cited source E1: (same as above)
LABEL L38.2 (S/P/N/C): S

Statement L38.3: One screen flag is attached: F000540 from SCR05, 'line date outside the claim window'.
  Cited source E1.s1:
      {"claim_id": "C0038238", "evidence_id": "E1.s1", "flag_id": "F000540", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
LABEL L38.3 (S/P/N/C): S

Statement L38.5: The duplicate check compared this member's other 7 claims and found no duplicate candidates.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "7 other claims for member M003631; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0038238", "tool": "find_duplicate_candidates"}
LABEL L38.5 (S/P/N/C): S

Statement L38.7: The provider intensity score is 0.14 (provider high-level share 0.176 vs peer median 0.162, 118 primary_care peers); this is a reason to look at claims, not a conclusion.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "51 visit lines for the provider; 118 primary_care peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.176"}, {"name": "provider_visit_lines", "value": "51"}, {"name": "peer_specialty", "value": "primary_care"}, {"name": "peer_count", "value": "118"}, {"name": "peer_median_share", "value": "0.162"}, {"name": "peer_mad", "value": "0.071"}, {"name": "peer_elevated_count", "value": "21"}, {"name": "score", "value": "0.14"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": [... 205 more characters not shown]
LABEL L38.7 (S/P/N/C): S

Statement L38.8: I could not find a policy sentence showing that a duplicate rule applies to this claim. The retrieved Medicare manual text defines exact duplicates for physician and supplier claims, but it does not link that definition to this claim. I did not write a quote from memory.
  Cited source clm104-ch01:264-265:0382:
      for analyzing duplicate claim receipts to
      determine whether certain providers are responsible for duplicates and, if so, identify
      those providers. The contractor should educate such providers to reduce the number of
      duplicates they submit. Should those providers continue to submit duplicate claims, the
      MAC should initiate program integrity action.
      B. Claims Submitted by Physicians, Practitioners, and other Suppliers (except
      DMEPOS Suppliers)
      Claims or claim lines that have been determined to be exact duplicates of another claim
      or claim line are denied. However, such denials may be appealed. An exact duplicate for
      physician and other supplier claims submitted to a MAC or carrier is a claim or claim line
      that exactly matches another claim or claim line with respect to the following elements:
      • Medicare beneficiary identifier;
      • Provider Number;
      • From Date of Service;
      • Thro [... 1025 more characters not shown]
LABEL L38.8 (S/P/N/C): C

NOTE L38: 38.1=S (all stated facts and values appear in the cited source(s)); 38.2=S (all stated facts and values appear in the cited source(s)); 38.3=S (all stated facts and values appear in the cited source(s)); 38.5=S (all stated facts and values appear in the cited source(s)); 38.7=S (all stated facts and values appear in the cited source(s)); 38.8=C (truncated excerpt and no full search listing prevent confirming search-wide absence)

==============================================================================
ITEM L39   (39 of 40)
Question the investigator asked: Summarise the evidence for claim C0033478, and quote what the policy sources say about any modifier or bundling issue it raises.
Answer status shown: ANSWERED
------------------------------------------------------------------------------
Statement L39.1: Claim C0033478 has one line (code X0021, 1 unit, billed 256.92) with service dates 2027-01-13 to 2027-01-15 and no modifiers on the line.
  Cited source E1:
      {"claim": {"claim_id": "C0033478", "diagnosis_codes": ["K1232"], "member_id": "M003661", "place_of_service": "PS2", "provider_id": "P0235", "service_from": "2027-01-13", "service_to": "2027-01-15", "total_billed": "256.92"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0033478", "evidence_id": "E1.s1", "flag_id": "F000497", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "256.92", "claim_id": "C0033478", "code": "X0021", "dx_pointer": 1, "line_id": "C0033478-01", "line_no": 1, "modifiers": [], "service_date": "2027-01-13", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service  [... 2795 more characters not shown]
LABEL L39.1 (S/P/N/C): S

Statement L39.2: The claim carries one screen flag, SCR05 'line date outside the claim window'.
  Cited source E1.s1:
      {"claim_id": "C0033478", "evidence_id": "E1.s1", "flag_id": "F000497", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
LABEL L39.2 (S/P/N/C): S

Statement L39.3: The service-date check found no line date outside the claim window; the line date 2027-01-13 falls inside the 2027-01-13 to 2027-01-15 window, so the flag and this check do not agree.
  Cited source E1.s1: (same as above)
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-01-13 to 2027-01-15 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0033478", "tool": "check_service_dates"}
LABEL L39.3 (S/P/N/C): S

Statement L39.4: The bundling check examined the one line against 14 synthetic bundle pairs and found 0 pair occurrences on a shared date, so no bundling finding was raised. The ruleset is invented, not NCCI.
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033478", "tool": "check_bundling"}
LABEL L39.4 (S/P/N/C): S

Statement L39.6: The duplicate check compared the claim with 11 other claims for the same member and found no duplicate candidates.
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "11 other claims for member M003661; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0033478", "tool": "find_duplicate_candidates"}
LABEL L39.6 (S/P/N/C): S

Statement L39.7: The policy search returned general NCCI text on modifiers. It does not address this claim's code, since no code pair occurred and no modifier is on the line.
  Cited source ncci-pm-ch01:17-18:0028:
      it should be used rather than modifier 59. Only if no more
      descriptive modifier is available, and the use of modifier 59 best explains the
      circumstances, should modifier 59 be used. Note: Modifier 59 should not be
      appended to an E/M service. To report a separate and distinct E/M service with a
      non-E/M service performed on the same date, see modifier 25.
      M
      odifier 59 and other NCCI PTP-associated modifiers should not be used to bypass a
      PTP edit unless the proper criteria for use of the modifier are met. Documentation in the
      medical record must satisfy the criteria required by any NCCI PTP-associated modifier
      used. Modifier 59 shall not be used with code 77427 ([CPT descriptor redacted]).
      N
      CCI PTP edits define when 2 procedure HCPCS/CPT codes may not be reported
      together, except under special circumstances. If an edit allows use of NCCI PTP-
      associated modifiers, the 2 procedur [... 929 more characters not shown]
LABEL L39.7 (S/P/N/C): C

NOTE L39: 39.1=S (all stated facts and values appear in the cited source(s)); 39.2=S (all stated facts and values appear in the cited source(s)); 39.3=S (all stated facts and values appear in the cited source(s)); 39.4=S (all stated facts and values appear in the cited source(s)); 39.6=S (all stated facts and values appear in the cited source(s)); 39.7=C (policy excerpt is cut and cited source does not show claim pair/modifier facts)

==============================================================================
ITEM L40   (40 of 40)
Question the investigator asked: Summarise the evidence for claim C0033145: what do the checks and flags show?
Answer status shown: CONFLICTING_EVIDENCE
------------------------------------------------------------------------------
Statement L40.1: The claim has one line (code X0017, 1 unit, billed 614.87) with service date 2027-02-15, and three diagnosis codes.
  Cited source E1:
      {"claim": {"claim_id": "C0033145", "diagnosis_codes": ["I4519", "I63031", "I82C22"], "member_id": "M003432", "place_of_service": "PS1", "provider_id": "P0134", "service_from": "2027-02-13", "service_to": "2027-02-15", "total_billed": "614.87"}, "evidence_id": "E1", "finding_count": 0, "flags": [{"claim_id": "C0033145", "evidence_id": "E1.s1", "flag_id": "F000491", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}], "lines": [{"billed_amount": "614.87", "claim_id": "C0033145", "code": "X0017", "dx_pointer": 1, "line_id": "C0033145-01", "line_no": 1, "modifiers": [], "service_date": "2027-02-15", "units": 1}], "notice": "Findings describe the data. They are not determinations.", "results": [{"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one cl [... 3260 more characters not shown]
  Cited source E1.r1:
      {"evidence_id": "E1.r1", "examined": "1 lines against 14 bundle pairs; 0 pair occurrences on a shared date", "findings": [], "limits": ["Bundle pairs are checked within one claim and one service date only."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_bundling"}
  Cited source E1.r2:
      {"evidence_id": "E1.r2", "examined": "1 lines; 1 have a unit limit", "findings": [], "limits": ["The limit applies to a single line. Units summed across lines or days are not checked."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "ruleset", "value": "synthetic-v1 (invented rules, not NCCI or MUE)"}], "subject": "C0033145", "tool": "check_unit_limits"}
LABEL L40.1 (S/P/N/C): S

Statement L40.2: Screen SCR05 flagged the claim with the text 'line date outside the claim window'.
  Cited source E1.s1:
      {"claim_id": "C0033145", "evidence_id": "E1.s1", "flag_id": "F000491", "screen_code": "SCR05", "screen_text": "line date outside the claim window"}
LABEL L40.2 (S/P/N/C): S

Statement L40.3: The service-date check compared the line date with the claim window 2027-02-13 to 2027-02-15 (both ends inclusive) and reported no finding.
  Cited source E1.r3:
      {"evidence_id": "E1.r3", "examined": "1 line dates against the claim window 2027-02-13 to 2027-02-15 (both ends inclusive)", "findings": [], "limits": ["Dates are compared with the claim's own window; no external calendar is used."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "window_bounds", "value": "inclusive"}], "subject": "C0033145", "tool": "check_service_dates"}
LABEL L40.3 (S/P/N/C): S

Statement L40.4: The bundling, unit-limit, duplicate-candidate, and code-validation checks reported no findings for this claim.
  Cited source E1.r1: (same as above)
  Cited source E1.r2: (same as above)
  Cited source E1.r4:
      {"evidence_id": "E1.r4", "examined": "8 other claims for member M003432; compared the multiset of (code, modifiers, units) per claim", "findings": [], "limits": ["Only the same member's claims are compared. Diagnoses and amounts are not part of the match.", "Near matches are shown for context; many are ordinary repeat services."], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "near_match_days", "value": "30"}], "subject": "C0033145", "tool": "find_duplicate_candidates"}
  Cited source E1.r5:
      {"evidence_id": "E1.r5", "examined": "1 procedure codes against the code table; 3 of 3 diagnosis codes against the ICD-10-CM list", "findings": [], "limits": [], "metrics": [], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "diagnosis_code_set", "value": "ICD-10-CM FY2027 billable codes"}], "subject": "C0033145", "tool": "validate_claim_codes"}
LABEL L40.4 (S/P/N/C): S

Statement L40.5: The claim has 0 findings in the dossier total, and one screen flag.
  Cited source E1: (same as above)
LABEL L40.5 (S/P/N/C): S

Statement L40.6: Provider P0134 intensity: 0.183 share of visit lines at the highest level versus a cardiology peer median of 0.200 (score -0.12, 3 of 41 peers elevated). This is a comparison score, not a conclusion about the provider.
  Cited source E1.r6:
      {"evidence_id": "E1.r6", "examined": "71 visit lines for the provider; 41 cardiology peers with at least 40 visit lines", "findings": [], "limits": ["A score is a reason to look at the claims, not a conclusion about the provider."], "metrics": [{"name": "provider_high_share", "value": "0.183"}, {"name": "provider_visit_lines", "value": "71"}, {"name": "peer_specialty", "value": "cardiology"}, {"name": "peer_count", "value": "41"}, {"name": "peer_median_share", "value": "0.200"}, {"name": "peer_mad", "value": "0.097"}, {"name": "peer_elevated_count", "value": "3"}, {"name": "score", "value": "-0.12"}], "notice": "Findings describe the data. They are not determinations.", "observations": [], "parameters": [{"name": "statistic", "value": "share of visit lines at the highest visit level"}, {"name": "score", "value": "modified z against same-specialty peers, subject excluded"}, {"name": "z_th [... 199 more characters not shown]
LABEL L40.6 (S/P/N/C): S

CONFLICT L40 (W/N): W
PATTERN L40 (F/O): F
NOTE L40: 40.1=S (all stated facts and values appear in the cited source(s)); 40.2=S (all stated facts and values appear in the cited source(s)); 40.3=S (all stated facts and values appear in the cited source(s)); 40.4=S (all stated facts and values appear in the cited source(s)); 40.5=S (all stated facts and values appear in the cited source(s)); 40.6=S (all stated facts and values appear in the cited source(s)); CONFLICT=W (date flag and no-finding date check concern the same line and window); PATTERN=F (only apparent disagreement is date flag versus check)
