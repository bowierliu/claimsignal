"use strict";
// Runs src/claims_copilot/api/web/app.js against a tiny fake DOM and checks the Ask tab.
// Usage: node web_smoke_ask.js APP_JS FIXTURES_JSON. Exits non-zero with a message on any failure.
// FIXTURES_JSON: { "views": [view, ...], "hostile": "<img ...>" }. Each POST to /workbench/ask
// returns the next view.
const fs = require("fs");
const vm = require("vm");

const [appPath, fixturePath] = process.argv.slice(2);
const fixtures = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

const created = [];

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.className = "";
    this._text = "";
  }
  append(...nodes) {
    for (const n of nodes) this.children.push(typeof n === "string" ? new FakeText(n) : n);
  }
  replaceChildren(...nodes) {
    this.children = [];
    this._text = "";
    this.append(...nodes);
  }
  removeChild(child) {
    this.children = this.children.filter((c) => c !== child);
  }
  get firstChild() {
    return this.children[0] || null;
  }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
  }
  removeAttribute(k) {
    delete this.attrs[k];
  }
  getAttribute(k) {
    return this.attrs[k] === undefined ? null : this.attrs[k];
  }
  addEventListener(type, fn) {
    (this.listeners[type] = this.listeners[type] || []).push(fn);
  }
  get textContent() {
    return this._text + this.children.map((c) => c.textContent).join("");
  }
  set textContent(v) {
    this._text = String(v);
    this.children = [];
  }
  set innerHTML(_v) {
    throw new Error("innerHTML was used");
  }
  click() {}
  focus() {}
  scrollIntoView() {}
  remove() {}
}
class FakeText extends FakeNode {
  constructor(text) {
    super("#text");
    this._text = String(text);
  }
}

const ids = [
  "status", "api-key", "health", "queue-form", "queue-out", "screen-code", "claim-form",
  "claim-id", "claim-out", "download", "entity-form", "entity-id", "entity-out", "policy-form",
  "policy-q", "policy-out", "ask-about", "ask-off", "ask-form", "ask-q", "ask-claim",
  "ask-submit", "ask-new", "ask-session", "ask-history", "ask-out",
];
const byId = Object.fromEntries(ids.map((id) => [id, new FakeNode(id)]));
const views = ["queue", "claim", "entity", "policy", "ask"];
const panels = Object.fromEntries(views.map((v) => [v, new FakeNode("section")]));
const buttons = Object.fromEntries(views.map((v) => {
  const b = new FakeNode("button");
  b.attrs["data-view"] = v;
  return [v, b];
}));

const document = {
  getElementById: (id) => byId[id],
  createElement: (tag) => {
    created.push(String(tag).toLowerCase());
    return new FakeNode(tag);
  },
  createTextNode: (t) => new FakeText(t),
  querySelector: (sel) => {
    let m = /^\[data-panel="(\w+)"\]$/.exec(sel);
    if (m) return panels[m[1]];
    m = /^nav \[data-view="(\w+)"\]$/.exec(sel);
    if (m) return buttons[m[1]];
    throw new Error("unexpected selector " + sel);
  },
  querySelectorAll: (sel) => {
    if (sel === "nav [data-view]") return Object.values(buttons);
    throw new Error("unexpected selector " + sel);
  },
  body: new FakeNode("body"),
};

const queue = fixtures.views.slice();
const requested = [];
const ok = (body) => ({ ok: true, json: async () => body });
const context = {
  document,
  Node: FakeNode,
  location: { hash: "" },
  history: { replaceState() {} },
  URL,
  URLSearchParams,
  Intl,
  Blob: class {},
  console,
  setTimeout,
  fetch: async (path, options) => {
    const clean = String(path).split("?")[0];
    requested.push({ path: String(path), options: options || {} });
    if (clean === "/v1/health") return ok({ status: "ok", claim_count: 3, policy_search: true });
    if (clean === "/workbench/ask/status") return ok({ enabled: true, policy_search: true });
    if (clean === "/workbench/ask" && options && options.method === "POST") {
      if (!queue.length) throw new Error("more asks than fixture views");
      const next = queue.shift();
      if (next && next.defer) {
        // Held back until the test resolves it, to act out a slow question.
        return new Promise((resolve) => { context.__pendingAsk = () => resolve(ok(fixtures.slow)); });
      }
      return ok(next);
    }
    if (clean === "/workbench/ask/reset" && options && options.method === "POST") {
      return ok({ cleared: true });
    }
    return { ok: false, json: async () => ({ title: "Not found", detail: "No fixture." }) };
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(appPath, "utf8"), context, { filename: "app.js" });

const tick = () => new Promise((r) => setTimeout(r, 20));
const submit = async (form) => {
  for (const fn of form.listeners.submit || []) fn({ preventDefault() {} });
  await tick();
};
const fail = (msg) => {
  console.error("FAIL: " + msg);
  process.exit(1);
};
const expect = (cond, msg) => {
  if (!cond) fail(msg);
};
const walk = (node, out = []) => {
  out.push(node);
  for (const c of node.children) walk(c, out);
  return out;
};
const out = byId["ask-out"];
const tags = () => walk(out).map((n) => String(n.tag).toLowerCase());
const ask = async (question, claim) => {
  byId["ask-q"].value = question;
  byId["ask-claim"].value = claim || "";
  await submit(byId["ask-form"]);
};

(async () => {
  await tick();
  byId["api-key"].value = "the-test-key";

  // 1. ANSWERED with hostile statement and source text.
  await ask("What did the checks find?", "C0000001");
  const answeredText = out.textContent;
  expect(answeredText.includes(fixtures.hostile), "hostile text shown literally: " + answeredText.slice(0, 300));
  expect(!tags().includes("img"), "no img element was created in the answer");
  expect(!created.includes("img") && !created.includes("script"), "no img/script element created at all");
  expect(walk(out).every((n) => Object.keys(n.attrs).every((k) => !k.toLowerCase().startsWith("on"))), "no event-handler attribute");
  expect(walk(out).every((n) => !n.attrs.href || n.attrs.href.startsWith("https:")), "only https links");
  expect(tags().includes("blockquote"), "the validated quote is shown in a blockquote");

  // 2. INSUFFICIENT_EVIDENCE: no blockquote at all. The helper clears the claim field before
  // submitting, mimicking "delete the field and press Ask": the view must never refill it
  // from the session (regression, 2026-11-16). Views 1 and 2 share one session whose claim is
  // C0000001 and whose follow-up named no claim, so a refill would re-pin the session.
  await ask("What about helicopters?");
  expect(out.textContent.includes("not enough evidence"), "insufficient message shown");
  expect(!tags().includes("blockquote"), "insufficient view renders no blockquote");
  expect(byId["ask-claim"].value === "", "a cleared claim field was refilled from the session");
  const sessionLine = byId["ask-session"].textContent;
  expect(sessionLine.includes("Claim in scope: C0000001"), "session line shows the claim in scope: " + sessionLine);
  expect(sessionLine.includes("The question named C0000240"), "the scope note is shown: " + sessionLine);

  // 3. INVALID_OUTPUT from validation: a could-not-be-validated message, no quote, no detail.
  await ask("And the modifier?", "");
  expect(/could not be validated/i.test(out.textContent), "invalid message shown: " + out.textContent.slice(0, 200));
  expect(!tags().includes("blockquote"), "invalid view renders no blockquote");
  expect(!out.textContent.includes("Error detail"), "a validation failure shows no error detail");

  // 4. INVALID_OUTPUT from a provider failure: service-failure framing, the safe adapter
  // error text in Run details, and nothing that reads like a validation failure.
  await ask("What did the checks find?", "");
  const failedText = out.textContent;
  expect(failedText.includes("The model service failed"), "service-failure label shown: " + failedText.slice(0, 200));
  expect(failedText.includes("Asking the question again may work."), "the retry hint is shown");
  expect(!/could not be validated/i.test(failedText), "no validation framing on a provider failure");
  expect(failedText.includes("Error detail") && failedText.includes("HTTP 529"), "the safe error detail is in Run details");
  expect(failedText.includes("charged at its estimate"), "a failed call's cost line is honest: " + failedText.slice(0, 400));
  expect(!tags().includes("blockquote"), "provider-failure view renders no blockquote");

  // 5. "New session" clicked while a question runs: the late answer is discarded, never
  // rendered, and the dead session token is not resurrected (reset-race regression,
  // 2026-11-16). The fixture defers this ask's response until __pendingAsk() fires.
  byId["ask-q"].value = "A slow question";
  byId["ask-claim"].value = "";
  await submit(byId["ask-form"]);  // starts askQuestion; its fetch stays pending
  for (const fn of byId["ask-new"].listeners.click || []) await fn({});
  expect(byId["ask-session"].textContent.includes("New session"), "reset shows the new-session line");
  expect(out.textContent === "", "reset cleared the panel");
  context.__pendingAsk();  // the stale question finally answers
  await tick();
  expect(byId["ask-session"].textContent.includes("New session"),
    "a late answer did not resurrect the old session: " + byId["ask-session"].textContent);
  expect(out.textContent === "", "a late answer was not rendered");
  expect(!byId["status"].textContent.includes("Searching"), "the searching status was cleared");

  // Every POST went to /workbench/ask or /workbench/ask/reset, as same-origin JSON without
  // ambient credentials.
  const posts = requested.filter((r) => (r.options.method || "GET").toUpperCase() === "POST");
  const askPosts = posts.filter((p) => p.path === "/workbench/ask");
  const resetPosts = posts.filter((p) => p.path === "/workbench/ask/reset");
  expect(askPosts.length === 5, "five asks posted, got " + askPosts.length);
  expect(resetPosts.length === 1, "one reset posted, got " + resetPosts.length);
  expect(posts.length === 6, "only asks and one reset posted, got " + posts.length);
  for (const p of posts) {
    expect((p.options.headers || {})["Content-Type"] === "application/json", "JSON content type");
    expect(p.options.credentials === "omit", "credentials omit");
  }
  for (const p of askPosts) {
    const body = JSON.parse(p.options.body);
    expect(typeof body.question === "string" && body.question.length > 0, "body has the question");
  }
  expect(JSON.parse(askPosts[1].options.body).session === fixtures.views[0].session.token, "the session token is sent back");
  expect(!("claim_id" in JSON.parse(askPosts[1].options.body)), "the cleared field sends no claim id");
  expect(JSON.parse(resetPosts[0].options.body).session === fixtures.views[3].session.token, "the reset names the active session");
  expect(requested.every((r) => r.path.startsWith("/")), "every request is same-origin");
  expect(requested.every((r) => !r.path.includes("the-test-key")), "key never in a URL");
  console.log("OK");
})().catch((err) => fail(String(err && err.stack ? err.stack : err)));
