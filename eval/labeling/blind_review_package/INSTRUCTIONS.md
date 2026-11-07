# Independent review: instructions

You are an independent reviewer. Work only from the files in this folder:

- `review_items.md` has the items to review. Each item has a question, an answer, and the exact
  text of every source the answer cites.
- `rubrics/faithfulness.md` and `rubrics/conflict.md` define the labels.
- `response_schema.json` describes the answer format.

Do not read any other file, search for other material, or use any tool other than reading these
files. Do not use outside knowledge: judge each statement only against the source text shown
under it.

## What to answer

Every line in `review_items.md` that starts with `LABEL`, `CONFLICT` or `PATTERN` is a prompt.
Give exactly one answer for every prompt, and no answer for anything else.

- `LABEL Rnn.k` (statement): one of `S` (SUPPORTED), `P` (PARTLY), `N` (NOT_SUPPORTED),
  `C` (CANNOT_TELL). Sources are shown in full, so use `C` only when a source is missing or
  garbled; spacing quirks are not a reason.
- `CONFLICT Rnn`: `W` (the conflict status is warranted) or `N` (not warranted), by
  `rubrics/conflict.md`.
- `PATTERN Rnn`: `F` if the only disagreement the answer reports is "a screen flag says X but the
  checks found nothing to support it"; `O` for anything else.

For a conflict item, the other statements shown are context for the CONFLICT and PATTERN prompts;
they have no LABEL prompt.

Sources named like `E1.f2` are results of deterministic checks over synthetic data, shown as JSON.
Sources named like `cms-...:12-13:ab12` are passages of public documents.

## Output

Reply with ONE JSON object and nothing else (no prose before or after). Keys are prompt ids as
written in the file, for example `"R03.2"` for `LABEL R03.2` and `"R07"` for `CONFLICT R07`:

```json
{
  "statement_labels": {"R03.2": "S"},
  "conflict_labels": {"R07": "W"},
  "conflict_patterns": {"R07": "F"}
}
```

Include every prompt in `review_items.md` under the matching key.
