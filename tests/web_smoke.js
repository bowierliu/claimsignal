"use strict";
// Runs src/claims_copilot/api/web/app.js against a tiny fake DOM and recorded API responses.
// Usage: node web_smoke.js APP_JS FIXTURES_JSON. Exits non-zero with a message on any failure.
const fs = require("fs");
const vm = require("vm");

const [appPath, fixturePath] = process.argv.slice(2);
const fixtures = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.listeners = {};
    this.hidden = false;
    this.value = "";
    this.className = "";
    this._text = "";
  }
  append(...nodes) {
    for (const n of nodes) this.children.push(typeof n === "string" ? new FakeText(n) : n);
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
  click() {}
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
  createElement: (tag) => new FakeNode(tag),
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

const requested = [];
const context = {
  document,
  Node: FakeNode,
  location: { hash: "" },
  history: { replaceState() {} },
  URL,
  URLSearchParams,
  Blob: class {},
  console,
  setTimeout,
  fetch: async (path, options) => {
    const clean = String(path).split("?")[0];
    requested.push({ path: String(path), options });
    if (!(clean in fixtures)) {
      return { ok: false, json: async () => ({ title: "Not found", detail: "No fixture.", request_id: "r1" }) };
    }
    return { ok: true, json: async () => fixtures[clean] };
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
const anyHref = (node) =>
  (node.attrs.href ? [node.attrs.href] : []).concat(...node.children.map(anyHref));

(async () => {
  await tick();
  expect(byId.health.textContent.includes("service ok"), "health line: " + byId.health.textContent);

  byId["api-key"].value = "the-test-key";
  await submit(byId["queue-form"]);
  expect(byId["queue-out"].textContent.includes(fixtures.__claim_id), "queue shows the claim id");
  expect(requested.some((r) => (r.options.headers || {})["X-API-Key"] === "the-test-key"), "key sent as header");
  expect(requested.every((r) => !r.path.includes("the-test-key")), "key never in a URL");
  expect(requested.every((r) => r.options.credentials === "omit"), "no ambient credentials");

  byId["claim-id"].value = fixtures.__claim_id;
  await submit(byId["claim-form"]);
  const claimText = byId["claim-out"].textContent;
  expect(claimText.includes("Claim " + fixtures.__claim_id), "dossier header");
  expect(claimText.includes("Checks"), "checks section");
  expect(!byId.download.hidden, "download offered after a dossier loads");
  expect(!panels.claim.hidden && panels.queue.hidden, "claim view is the visible panel");

  byId["policy-q"].value = "modifier";
  await submit(byId["policy-form"]);
  const policyText = byId["policy-out"].textContent;
  expect(policyText.includes(fixtures.__hostile), "hostile source text is shown as literal text");
  expect(policyText.includes("source text, untrusted"), "source text is labelled untrusted");
  expect(anyHref(byId["policy-out"]).every((h) => h.startsWith("https:")), "only https links");

  byId["entity-id"].value = "C9999999";
  await submit(byId["entity-form"]);
  expect(byId["entity-out"].textContent.includes("Not found"), "an API error is shown, not thrown");
  console.log("OK");
})().catch((err) => fail(String(err && err.stack ? err.stack : err)));
