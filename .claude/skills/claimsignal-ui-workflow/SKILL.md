---
name: claimsignal-ui-workflow
description: Use for ANY change to the ClaimSignal evidence workbench front end (index.html, style.css, app.js or favicon.svg served under /workbench), including design reviews, redesign proposals, UI polish, new components, copy edits and bug fixes. Covers how to review the running page and propose before editing, how to work inside the strict CSP, no-innerHTML, no-third-party, read-only and fixed-endpoint rules, and the self-check to run before calling a change done. Read this first, before the other claimsignal skills.
---

# ClaimSignal workbench: changing the UI safely

## Why this page is unusual

The workbench is a portfolio piece that its owner, Bowie, demos live in a job interview on a shared screen. Three things follow, and they explain every rule below.

- **He has to explain every line.** Small, plain code beats clever code. A helper he can't describe in one sentence is a liability, even if it works.
- **The security posture is part of the demo.** A strict Content Security Policy, a DOM built only with `textContent`, and no third-party code are things he points at. A change that weakens them defeats the purpose even if the page looks better. Tests check some of this.
- **The product never decides anything about a claim.** It shows evidence and a human investigator decides. A screen that looks like a verdict is a bug of the same rank as a crash.

## The loop

1. **Look before you read code.** Open `http://127.0.0.1:8000/workbench` in the browser and visit all four views using the demo IDs below. Screenshot the dossier at 1280×720, which is close to what a projector audience sees. If you cannot reach the page (server down, no browser tool), say so and ask. Do not review from source alone and present it as something you saw.
2. **Read the four files in full.** They are small (about 120 lines HTML, 240 CSS, 440 JS). Find the `el()` helper and its attribute allowlist, how views switch, the renderer for each view, and any tests that cover the static files or the CSP header.
3. **Describe it back** in one short paragraph: layout, hierarchy, and the dossier's reading order from top to bottom. The point is to let Bowie confirm you saw the same page he sees.
4. **Propose a ranked list, eight items at most,** in the format below.
5. **Stop and wait for him to pick.** No file changes before that.
6. **Implement one picked item at a time,** following "Implementing" below.
7. **Run the self-check, then report** in the report format.

Demo IDs: `C0000493` bundling finding · `C0001297` unit-limit finding · `C0001401` date-window finding · `C0040001` duplicate finding · `C0000791` flag raised, nothing found · `P0011` provider with high visit-level intensity · policy search `mutually exclusive code pairs`.

## Proposal format

For each item give:

- **Problem**: what a viewer fails to see or misreads today.
- **Change**: concrete enough to picture.
- **Files**: which of the four it touches.
- **Size**: small (under 30 minutes), medium, or large.
- **Needs from you**: only if it needs data the API does not return, or a judgment call.

Rank by his priorities, in this order: (1) the dossier's main result is obvious within 10 seconds: what was found, where, and what could not be checked; (2) found / nothing found / not scored look distinct without relying on color; (3) provider versus peers shown visually; (4) a shorter header; (5) polish.

He has listed what he thinks is weak. Check each point against the running page and say whether you confirm it, would correct it, or found something he missed. Repeating his list back adds nothing.

## Rules, and what to do instead

| Rule | Rules out | Do this instead |
|---|---|---|
| CSP `style-src 'self'` | `style=""` attributes, `<style>` blocks, `setAttribute('style', …)`, `cssText` | Add a class in `style.css` and toggle it with `classList`. Show and hide with the `hidden` attribute. For sizes or positions that depend on data, use SVG geometry attributes (see `claimsignal-svg-charts`). Browsers do let `node.style.width = …` through this policy, but do not use it here: "all styling lives in style.css" is something Bowie says out loud, so keep it literally true. |
| CSP `script-src 'self'` | Inline `<script>`, `onclick=""` attributes, `javascript:` URLs | `addEventListener` in `app.js`. |
| CSP `default-src 'none'`, `img-src 'self'`, `connect-src 'self'` | CDNs, web fonts, remote images, and `data:` URIs (a CSS `url("data:…")` background is blocked too) | The system font stack already in use. Shapes drawn with CSS borders and radii, CSS gradients for patterns, or inline SVG built with DOM calls. |
| No `innerHTML` | `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `DOMParser`, markup in template strings | Build nodes with `el(tag, props, ...children)`. Empty a container with `replaceChildren()`. Text always goes in through `textContent`. If you need an attribute `el()` does not allow, add that one name to the allowlist and mention it in your report. |
| API values are text | Building a class name, id, attribute name or URL by concatenating an API value | Map API values to classes through a fixed lookup table with a neutral default. An unexpected value then renders plainly instead of producing a surprise. |
| No build step, no third-party code | Frameworks, npm, icon sets, chart libraries, preprocessors | Vanilla HTML, CSS and JS in the four existing files. Do not add a fifth file without asking. |
| Read-only | Any control that acts on a claim: approve, deny, escalate, assign, resolve, mark reviewed, save, edit | Allowed interactions: navigate, open, filter, search, expand or collapse, download the evidence JSON. |
| Fixed endpoints | New routes, new query parameters, fanning out many requests to decorate a list | Use what the eight endpoints return. Otherwise see the next section. |
| Accessibility floor | Removing the skip link, labels, focus rings or `aria-live` regions; meaning carried by color alone; information available only on hover | Keep what exists. Give anything color-coded a text label and a shape as well. Text contrast at least 4.5:1; marks and borders that carry meaning at least 3:1. |
| Synthetic data only | Realistic member names, real procedure or diagnosis codes, real provider names in placeholders or examples | IDs shaped like `C0000493`, `P0011`, `M002990`, `X0032`. |
| No verdicts | See `claimsignal-evidence-ui` | |

The eight endpoints: `GET /v1/health`, `/v1/flags?screen_code=&limit=&after=`, `/v1/claims/{id}/dossier`, `/v1/providers/{id}`, `/v1/providers/{id}/intensity`, `/v1/providers/{id}/peers?limit=`, `/v1/members/{id}/history?limit=`, `/v1/policy/search?q=`.

## When the design needs something the data does not have

Stop and tell Bowie which field you need and what it would let the page show. He decides whether to change the API. Likely cases:

- A marker in the flag queue for flags whose checks found something. `/v1/flags` may not carry that.
- A machine-readable "not scored" status, if the only signal today is a sentence of prose.
- Each peer's individual value for a distribution chart, if the peers endpoint returns only identifiers.

Do not work around a gap by fetching one dossier per table row, parsing meaning out of prose strings, inventing a number, or hard-coding values for the demo IDs. Each of those makes the page claim something the system does not actually know, and an interviewer who asks "where does that come from?" will find it.

## Implementing

- Make the smallest diff that achieves the effect. Do not reformat, rename or reorder code you are not changing.
- Extend the design tokens. Add new custom properties to `:root` beside related ones, and leave existing values alone unless changing one is the item itself.
- One picked item is one change set, and the page works after each.
- Prefer what the platform already does over new code: `<details>` for collapsing, the `hidden` attribute, anchors for jump links, `Intl.NumberFormat` for numbers, CSS for simple shapes.
- New JS goes in small named functions of about 25 lines or less. Comment the reason for anything non-obvious, not what the line does.
- Keep a line budget. Report the net change per file, and if an item pushes `app.js` up by more than about 60 lines, say so and offer a simpler version.

## Self-check before reporting

Run these from the folder that holds the four files.

```bash
# 1. HTML injection sinks: expect no output
grep -nE 'innerHTML|outerHTML|insertAdjacentHTML|document\.write|DOMParser|createContextualFragment' app.js

# 2. Inline styles, scripts and handlers: expect no output from any of these
grep -nEi '<style|[[:space:]]style=|[[:space:]]on[a-z]+=' index.html
grep -nEi '<script' index.html | grep -v 'src='
grep -nE "\.style\b|cssText|setAttribute\(['\"]style" app.js

# 3. Anything the page loads must be same-origin: review every hit.
#    Links a person clicks are fine. src, <link href>, url() and fetch targets are not.
grep -nE 'https?:|url\(' index.html style.css app.js | grep -v 'www.w3.org/2000/svg'

# 4. Every request path is one of the eight endpoints: review each line
grep -n '/v1/' app.js

# 5. Verdict vocabulary: review every hit (see claimsignal-evidence-ui for what is acceptable)
grep -nEi 'fraud|suspicious|abus|improper|violation|risk|denial|deny|approv|reject|clean|pass(ed)?\b|fail(ed)?\b' index.html app.js

# 6. Size
wc -l index.html style.css app.js
```

Then run the project's test suite the way the repository documents it. If a test fails because it asserts something you changed on purpose, such as exact header text, stop and report it. Do not edit the test to make it pass.

In the browser:

- Hard-reload with the developer console open and exercise the view you changed. There should be no message beginning "Refused to", which is how a CSP violation appears, and no errors. A violation only fires when the offending code runs, so a clean console on a view you did not open proves nothing.
- Network panel: only same-origin requests, to the four static files and the listed `/v1/` endpoints.
- Keyboard only: Tab from the address bar. The skip link appears first, everything interactive is reachable, the focus ring is visible, and nothing new needs a mouse or a hover.
- Emulate `prefers-reduced-motion`: nothing moves.
- At 620px wide and below: no horizontal page scroll. Tables may scroll inside their own container.
- At 1280×720 and 150% zoom: the changed area still makes sense.
- Load `C0000493` (a finding), `C0000791` (flag raised, nothing found), and a "not scored" case if one exists in the data.

## Report format

After each change, report exactly these four things:

- **Changed**: files and net lines, in a sentence or two.
- **Verify in the browser**: the exact clicks and demo ID, and what should be visible.
- **Say to an interviewer**: one or two plain sentences giving the reason for the change, not a description of the code.
- **Not verified**: anything you could not check, and why. Write "nothing" only if that is true.

Example:

> **Changed**: `app.js` +14, `style.css` +9. Clean checks in the dossier now render inside `<details>`, closed by default.
> **Verify in the browser**: Claim dossier → `C0000493` → the bundling card is open, the other five show one line each and open with a click or Enter.
> **Say to an interviewer**: "Five of the six checks found nothing, so they collapse to one line each and the one finding is what you see first. The collapse is the browser's own details element, so it needed no JavaScript and works from the keyboard."
> **Not verified**: I could not find a claim with a not-scored check, so that state is untested.
