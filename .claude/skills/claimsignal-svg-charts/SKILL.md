---
name: claimsignal-svg-charts
description: How to draw small charts in the ClaimSignal workbench with hand-written inline SVG created through DOM calls, with no chart library, no innerHTML and no inline styles, so the strict CSP still holds. Use whenever a task involves a chart, graph, plot, distribution, dot plot, number line, meter, bar or sparkline, any request to show provider, peer or intensity data visually, or any SVG element created from app.js. Includes a tested helper and a provider-versus-peers dot plot.
---

# ClaimSignal workbench: charts under a strict CSP

Read `claimsignal-ui-workflow` for the rules and `claimsignal-evidence-ui` for wording. This skill covers the one thing those rules make awkward: drawing a chart with no library, no `innerHTML` and no inline styles.

## The technique

Three facts make it work.

1. **SVG elements need a namespace.** `document.createElement('svg')` produces an unknown HTML element that draws nothing. Use `document.createElementNS('http://www.w3.org/2000/svg', tag)`. That URL is a name, not a network request, so it does not touch the CSP.
2. **Geometry goes in attributes, appearance goes in the stylesheet.** Position and size (`x`, `y`, `cx`, `cy`, `r`, `x1`…`y2`, `points`, `viewBox`) are plain attributes, so data-driven layout needs no inline style. Color, stroke, dash pattern, font size and text alignment come from classes in `style.css`.
3. **SVG text is colored with `fill`, not `color`,** and aligned with `text-anchor`, both set in CSS.

Add one helper beside `el()` with the same contract: a fixed attribute list, and text only through `textContent`. Read `el()` first and match its style. This version is tested:

```js
const SVG_NS = 'http://www.w3.org/2000/svg';
const SVG_ATTRS = new Set(['viewBox', 'class', 'role', 'id', 'aria-labelledby',
  'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'points']);

// Same contract as el(): a fixed attribute list, and text only through textContent.
function svg(tag, attrs, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (name === 'text') node.textContent = value;
    else if (SVG_ATTRS.has(name)) node.setAttribute(name, String(value));
    else throw new Error('svg(): attribute not allowed: ' + name);
  }
  node.append(...children);
  return node;
}
```

`style`, `fill`, `stroke`, `transform` and event attributes are deliberately absent from the list. If you find yourself wanting one, the answer is a class.

## Look at the data before choosing a chart

Request `/v1/providers/P0011/intensity` and `/v1/providers/P0011/peers` and list the fields you actually get. Then choose:

| The payload gives you | Draw |
|---|---|
| The provider's value, the peer median, the cutoff, and each peer's own value | A dot plot: one hollow dot per peer, with the median, the cutoff and the provider marked |
| The provider's value, the median and the cutoff, but no per-peer values | The same axis with the three marks and no dots (pass an empty `peers` array) |
| A "not scored" result | No chart. Show the not-scored state and its reason in the same space, so the layout does not jump |

Do not draw anything the data does not contain. No bell curve, no smoothed density, no invented peers. A drawn distribution is a claim about the peers, and a data-science audience will ask where it came from. If per-peer values would make the chart much better and the endpoint does not return them, tell Bowie; that is an API decision, not a front-end one.

**Which unit goes on the axis.** The natural unit (share of visit lines at the top level, 0% to 100%) reads faster than a z-score for a mixed audience, so prefer it and put the z-score in the caption. That only works if the cutoff is available in the same unit. If the API gives the cutoff only as a z-score and does not give what is needed to convert it, draw the axis in z units instead. Do not re-derive the statistic in the browser; plot what the API returns.

If the provider belongs to its own peer list, leave it out of the dots so it is not drawn twice.

## The provider-versus-peers dot plot

Tested with jsdom and rendered at projector size. Adapt the field names to the real payload.

```js
// Every value is in the same unit (for example share of visit lines, 0 to 1).
// labels = { provider, median, cutoff, min, max }: text already formatted by the caller.
function peerDotPlot({ provider, peers, median, cutoff, min, max, labels }) {
  const W = 640, H = 150, PAD = 48, AXIS = 104, R = 5;
  const x = v => PAD + (Math.min(Math.max(v, min), max) - min) / (max - min) * (W - 2 * PAD);
  const side = v => (x(v) < 100 ? 'at-start' : x(v) > W - 100 ? 'at-end' : 'at-middle');
  const label = (v, y, text) => svg('text', { class: 'chart-label ' + side(v), x: x(v), y, text });
  const rule = (v, cls) => svg('line', { class: cls, x1: x(v), y1: 30, x2: x(v), y2: AXIS + 6 });

  const stack = {}; // peers that land in the same column pile upward, one dot per peer
  const dots = peers.map(v => {
    const col = Math.round(x(v) / (2 * R));
    stack[col] = (stack[col] || 0) + 1;
    return svg('circle', { class: 'chart-peer', cx: col * 2 * R, cy: AXIS - R - 2 - (stack[col] - 1) * 2 * R, r: R - 1 });
  });

  const px = x(provider), py = AXIS - 9; // provider marker: a diamond, so shape (not color) sets it apart
  return svg('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart', role: 'img', 'aria-labelledby': 'peer-chart-title' },
    svg('title', { id: 'peer-chart-title', text: 'Dot plot: this provider compared with same-specialty peers' }),
    svg('line', { class: 'chart-axis', x1: PAD, y1: AXIS, x2: W - PAD, y2: AXIS }),
    ...dots,
    rule(median, 'chart-median'), rule(cutoff, 'chart-cutoff'),
    svg('polygon', { class: 'chart-provider', points: `${px},${py - 9} ${px + 9},${py} ${px},${py + 9} ${px - 9},${py}` }),
    label(provider, 18, labels.provider),
    label(median, AXIS + 22, labels.median), label(cutoff, AXIS + 40, labels.cutoff),
    svg('text', { class: 'chart-label at-end', x: PAD - 12, y: AXIS + 4, text: labels.min }),
    svg('text', { class: 'chart-label at-start', x: W - PAD + 12, y: AXIS + 4, text: labels.max }));
}
```

How it reads, and why it is built this way:

- **Each hollow dot is one peer.** Dots are binned into columns about 2% of the axis wide and stacked, which is what a dot plot is. Nothing is smoothed.
- **The provider is a filled diamond** with its ID and value directly above it. It differs from the peers in shape and fill as well as color.
- **The peer median is a dashed rule and the screen's cutoff is a solid rule,** each labelled in words on its own row so the labels cannot collide. They are told apart by dash pattern and label, not hue.
- **Labels sit on the marks. There is no legend,** so nobody has to look away from the data to decode it.
- **The cutoff is neutral.** Use the same ink as the median, with no red and no shaded zone beyond it. Label it "screen cutoff". Past the cutoff is where the screen raises a flag. It is not a conclusion about the provider.
- Labels near an edge switch anchor through `side()` so they stay inside the frame.

Guard the inputs before calling it. If the provider value, median or cutoff is null, `NaN` or infinite, or `max` equals `min`, do not draw; show the not-scored state with whatever reason the payload gives. With more than about 60 peers the stacks grow into the label row, so switch to counted bars per bin or ask.

The matching CSS. Use the real custom property names from `:root`; these follow the token names in the design brief.

```css
.chart-wrap { overflow-x: auto; }                      /* narrow screens scroll, like the tables */
.chart { display: block; width: 100%; min-width: 480px; height: auto; }
.chart-axis { stroke: var(--muted); stroke-width: 1.5; }
.chart-peer { fill: none; stroke: var(--muted); stroke-width: 1.5; }
.chart-median { stroke: var(--ink); stroke-width: 2; stroke-dasharray: 5 4; }
.chart-cutoff { stroke: var(--ink); stroke-width: 2; }
.chart-provider { fill: var(--accent); stroke: var(--panel); stroke-width: 2; }
.chart-label { fill: var(--ink); font-size: 13px; }    /* SVG text takes fill, not color */
.chart-label.at-start { text-anchor: start; }
.chart-label.at-middle { text-anchor: middle; }
.chart-label.at-end { text-anchor: end; }
```

Font size inside an SVG is in viewBox units, so it scales with the chart. At a 640-unit viewBox drawn about 960px wide, 13 units is close to 20px, which suits a projector. The `min-width` keeps it readable on narrow screens.

## The caption carries the numbers

Put one sentence of real text directly under the chart, built from the same values. It is what a screen reader user gets, what survives a bad projector, and what an interviewer reads aloud. Shape it like this, using the payload's own terms for the statistic:

> P0011: 74.1% of visit lines at the top level. Peer median 41% across 34 same-specialty peers. Modified z-score 4.2; the screen's cutoff is 3.5. This describes the data. It is not a determination.

Those numbers are placeholders that show the shape. Take every value from the API and format it with the `Intl` helpers from `claimsignal-evidence-ui`.

## Accessibility

- The SVG has `role="img"` and a short `<title>` naming what kind of chart it is. The caption does the explaining.
- Keep the existing peer list on the page. It is the chart's data table.
- Every mark that carries meaning uses ink, muted or accent, each of which clears 3:1 against the panel. Do not draw marks in the line or sky colors; they are around 1.4:1.
- No animation and no hover-only detail.
- Only one chart with this title id should exist on the page at a time. If a second chart is ever added, pass the id in.

## Check it

- Console: no "Refused to" messages after the chart renders.
- `P0011` shows a diamond, both rules and their labels with nothing overlapping.
- A provider that is not scored shows the not-scored state, not an empty axis.
- Grayscale emulation: the provider, median and cutoff are still distinguishable.
- 620px width: the chart scrolls inside its wrapper and the page does not.
- Budget: helper about 15 lines, chart about 25, CSS about 11. If it grows much past that, simplify.

## What to say about it

- "The chart is about forty lines of plain JavaScript. It uses createElementNS and setAttribute against a fixed attribute list, so the no-innerHTML rule holds for SVG as well."
- "Positions are SVG attributes and appearance is in the stylesheet, so the Content Security Policy stays at style-src 'self' with no exceptions."
- "Each dot is one peer provider. I did not fit a curve, because that would show a distribution I have not measured."
- "The cutoff is labelled as the screen's cutoff. Crossing it is why a flag was raised. It is not a finding about the provider."
