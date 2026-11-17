---
name: claimsignal-evidence-ui
description: Design patterns and wording rules for showing investigation evidence in the ClaimSignal workbench without implying a verdict. Use whenever designing or changing how claim dossiers, checks, findings, flags, statuses, summaries, badges, colors or copy appear, including the dossier summary, the found / nothing found / not scored states, card hierarchy, number and label formatting, the header and notice, the flag queue, and projector legibility. Use it even for a one-word copy change, because wording is where a verdict slips in.
---

# ClaimSignal workbench: evidence-first design

Read `claimsignal-ui-workflow` first for the technical rules. This skill is about what the page should say and how it should look.

## What the page is for

A viewer should be able to answer three questions about a flagged claim in about ten seconds on a projected screen: what did the checks find in the data, where exactly (claim, line, rule), and what could the checks not see. A fourth answer must always be visible: a human investigator decides.

The page never answers "is this claim bad?" Every design choice either describes evidence or describes a limit. If a choice does neither, cut it.

## Four states, each told apart three ways

Projectors wash out pale tints, and a share of any audience has a color-vision deficiency. So each state differs in mark shape, in a text label, and in border style. Color comes last, as reinforcement.

| State | It means | Text label, always visible | Mark | Card edge | Default |
|---|---|---|---|---|---|
| Finding | The check found something in the data | "1 finding", "2 findings" | Filled disc | Thick solid edge in accent or ink | Open |
| Nothing found | The check ran on the data it could see and found nothing | "Nothing found" | Hollow ring | Thin solid edge, muted title | Collapsed |
| Not scored | The check could not evaluate, for example too little data | "Not scored" plus the reason from the payload | Short horizontal dash | Dashed edge in the warn color | Collapsed, with the reason on the visible line |
| Load error | The software failed | The existing error card | Existing | Existing red border | Not applicable |

What each color means, so the whole page stays consistent:

- **Accent blue or ink**: evidence is present.
- **Muted**: the check ran and found nothing.
- **Amber (warn)**: a limit or caveat of the tool: not scored, untrusted source text, the notice box.
- **Red (bad)**: the software failed. Never use red for a finding. Red on a claim reads as "this claim is bad", which is a verdict.
- **No green and no tick marks anywhere.** A tick on "Nothing found" says the claim is fine, and the check cannot know that. It only knows it found nothing in the data it could see. Avoid the word "clean" for the same reason, and because "clean claim" is a term of art in claims processing.

Draw the marks with CSS (a small inline-block with a border, a border-radius and optionally a background) so they need no images, no icon font and no extra JS. Unicode symbols render differently across operating systems, so do not depend on them for meaning.

## Work out the state from the data

- **Finding**: the result's `findings` array has at least one entry.
- **Not scored**: look at the real dossier JSON, and at `/v1/providers/{id}/intensity`, to see how "could not evaluate" is signalled: a field in `metrics` or `observations`, a null score, or only a sentence of prose. If prose is the only signal, do not match on the sentence. Tell Bowie that a status field is needed and show "Nothing found" versus "Not scored" only where the data lets you tell them apart reliably.
- **Nothing found**: the check ran, has zero findings, and is not "not scored".
- **Load error**: the request failed.

Keep the mapping in one small function that returns one of four fixed strings. Everything else (mark, label, class, open or closed) keys off that string through a lookup table.

## Dossier reading order

Most important first:

1. **Summary panel**, new, directly under the claim form.
2. **Checks with findings**, open.
3. **Claim header and Lines table**, as context for the finding.
4. **Remaining checks**, one line each, collapsed.
5. **Flags table.**

The summary panel alone delivers most of the benefit. Reordering sections is a separate, optional item; propose them separately so Bowie can take the small one first.

### The summary panel

Build it only from `finding_count`, `results[]` and `flags`. It holds:

- **One headline sentence**, the largest text on the page after the h1. Templates:
  - One or more findings: "1 of 6 checks found something in the data: Bundling."
  - A flag but no findings: "A screen flagged this claim. None of the 6 checks found anything in the data they examined."
  - Add when relevant: "1 check could not be scored: Provider intensity (reason from the payload)."
- **The finding itself**: the API's own `summary` text, verbatim, followed by its evidence locator (claim, line, rule). Never paraphrase a finding into stronger words than the API used.
- **A row of six status chips**, one per check, each showing mark + name + label. Each chip jumps to its card. First check how views switch: if the page already uses the URL hash for navigation, do not use anchor links. Use a click handler that opens the target `<details>`, calls `scrollIntoView()` and moves focus, with no smooth scrolling under reduced motion.
- **The existing notice**: "Findings describe the data. They are not determinations."

Leave out anything the data does not give you: scores, dollar totals presented as exposure, severity levels, rankings, or words like "top" and "worst".

### Inside a check card

Use three levels of emphasis and no more. Create them with size, weight and spacing, not with more boxes. A finding card inside a check card inside a section is three nested rounded boxes; flatten the innermost into a block with a left rule.

1. **Primary**: the title row (mark, human title, status label) and the finding summary, which is the largest text in the card.
2. **Secondary**: the evidence locator and the key/value details. The locator is the "where", so give it its own labelled row directly under the summary, with claim, line and rule in monospace. It should not sit in a muted footer.
3. **Tertiary**: the "Examined" line, "What this check could not see", and the notice. Smaller and lighter, but still at least 4.5:1 contrast and never hidden on a card that has a finding.

Titles: show a human name ("Bundling") from a fixed lookup keyed on `tool`, with the raw tool name (`check_bundling`) beside it in small monospace so the card traces back to the code. An unknown tool falls back to its raw name.

Collapse the nothing-found and not-scored cards with a native `<details>` element. Its `<summary>` line carries the mark, title and label, so the state is readable while closed.

If a finding's evidence identifies line numbers in a structured field, mark those rows in the Lines table with a small text tag such as "in bundling finding". If the line numbers only appear inside prose, leave the table alone.

## Wording

- **Use**: found, shows, matches, differs from, examined, flagged by a screen, could not see, not scored, cutoff used by the screen.
- **Avoid**: fraud or fraudulent, suspicious, abuse, improper, violation, risk or risky, red flag, alert, clean, pass, fail, cleared, approved, denied, overbilled, and any tick or cross. The exception is the notice that says what the page does not decide.
- "Flag" means a screen raised it. "Finding" means a check found something in the data. They are different things, and `C0000791` is the case that proves it. Never use one word for both.
- Keep the API's hedges. "Duplicate candidate" must not become "duplicate".
- Pluralize properly ("1 finding", "2 findings"). Sentence case. No exclamation marks.

## Numbers, dates and labels

Use the built-in `Intl` formatters, created once at the top of `app.js`:

```js
const fmtInt = new Intl.NumberFormat('en-US');
const fmtNum = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const fmtPct = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 });
const fmtUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const plural = (n, one, many = one + 's') => `${fmtInt.format(n)} ${n === 1 ? one : many}`;
```

- Decide the format per known key through a small map (for example a share key uses `fmtPct`, `total_billed` uses `fmtUsd`). Do not guess from the value: 0.74 could be a share or a ratio. A numeric key that is not in the map gets `fmtNum`, which turns `0.7412587412587412` into `0.74`.
- Rounding is for display only. The evidence download keeps full precision; say so if asked.
- Show date-only values as the ISO text the API sends (`2024-03-01`). Do not pass them through `new Date()`: a date-only string is parsed as midnight UTC and displays as the previous day in US time zones.
- Humanize keys with a small label map (`service_from` becomes "Service from"), falling back to replacing underscores with spaces. Keep IDs and codes in monospace.
- Wherever a comparison with peers appears, show the size of the peer group if the payload gives it.

## Header and notice

Content should start in roughly the top quarter of a 1280×720 screen.

- Put the logo and name on the left and the service status pill on the right, in one row.
- Keep the notice, in full, visible in every view. It can become a slim full-width bar, but do not shorten, truncate or collapse it. It is the product's safety statement.
- The four badges repeat the notice. Fold them into the notice bar or move them to the footer.
- Move the API key field into a closed `<details>` labelled "API key (optional)". Keep its `<label>`.
- Keep the `aria-live` status region and the skip link.

## Legibility on a shared screen

- Nothing below 13px. The headline result at least 18px.
- The text colors in the current tokens all clear 4.5:1 on the cream and panel backgrounds. The quiet tokens do not carry meaning at a distance: the line color on the panel is about 1.4:1, the sky fill on the panel about 1.4:1, and panel on cream about 1.1:1. So do not let a state depend on a line-colored border, a sky fill or a card's background tint. Use ink, accent or warn for any edge or mark that means something.
- That applies to the active navigation tab as well. A sky fill alone is a color-only cue at low contrast. Give it a second cue such as an ink underline or heavier weight.
- No information on hover only. Nobody hovers on a projector.

## Flag queue

- When a filter is active, say so in the summary line and offer a clear control: "Showing 50 of 124 flags for screen X" with "Clear filter".
- Give the empty result its own message.
- Any grouping or count computed in the browser covers only the rows loaded so far. Label it that way, or leave it out.
- Whether a flag's checks found something is not in `/v1/flags` unless the payload says so. Ask before designing around it.
- Do not sort or badge flags by anything that reads as severity.

## Before you call it done

Screenshot the dossier at 1280×720, 100% zoom, without scrolling, and answer from the screenshot alone:

1. What was found?
2. Where: which claim, line and rule?
3. What could not be checked?
4. Who decides?

Do this for `C0000493` (a finding), for `C0000791` (flag raised, nothing found; it must look neither broken nor like an all-clear), and for a not-scored case if the data has one. Then switch the browser's rendering emulation to grayscale (achromatopsia) and confirm the states are still distinguishable.
