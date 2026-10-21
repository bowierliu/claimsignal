# Phase 9 report: workbench UI

Status: complete under the owner's standing instruction of 2026-10-20 (no per-phase approval gate).
Phase 10 starts after this report.

## 1. Executive summary

An investigator can now open `/workbench` on the API (`uv run python -m claims_copilot.api`, then
`http://127.0.0.1:8000/workbench`) and work through a flag: pick a flag from the queue, open the claim
dossier (claim, lines, flags, every check's findings, evidence references, what each check could not
see, and the "this is not a decision" notices), follow a link to the provider or member, search the
cited public policy sources, and download the dossier as JSON.

It is read-only and does not call a model. That is a real limit, not a design triumph: the project's
cited evidence summary is produced by the agent, which the UI does not run and cannot show (KF-051).

The page is three static files with no third-party code. Source text is untrusted and shown as plain
text under an "untrusted source text" label, with source, pages, retrieval date, and hash.

## 2. Metrics and spend

| Item | Value |
|---|---|
| Files | `api/web/index.html`, `app.js`, `style.css`; `api/workbench.py` |
| Tests | 12 new in `tests/test_api_workbench.py` (headers, file whitelist, contract unchanged, key rule, unsafe-sink scan, no inline code, same-origin requests, `node --check`, fake-DOM run on real API payloads with hostile text) |
| Spend | $0.00. Project total about $2.99 of $50 |

No usability claim is made. Nobody has used the page.

## 3. Failures and open risks

- KF-051: no agent summary in the UI.
- KF-052: not opened in a real browser; no accessibility audit; layout unverified. The fake-DOM run
  proves the script handles real payloads without error and renders hostile text as text.
- The page files are served without the key (the data is not).
- One shared key for all users (KF-049).

## 4. Decisions made on the owner's behalf

In `DECISIONS.md` ("Phase 9"): static files over a framework; served by the API outside the OpenAPI
contract; page open, data behind the key; text-only rendering; read-only scope with no "investigate"
button; no audit route; fake-DOM testing instead of a browser.

## 5. Teach-me list

1. **Content security policy.** What does `script-src 'self'` stop, and why is it still not a
   substitute for never inserting API text as HTML?
2. **Why the page files can be public while the data is not.** What is on the wire for each?
3. **Untrusted text in a trusted frame.** Why a policy passage is labelled and shown as a quote
   rather than rendered as part of the page's own message.
