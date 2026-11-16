"use strict";
/*
 * Read-only evidence viewer over the /v1 API, plus "Ask the agent", which POSTs a question to
 * /workbench/ask (same origin, JSON) and renders the server's validated answer view.
 *
 * Safety rules for this file (checked by tests/test_api_workbench.py):
 *  - Everything from the API is written with textContent or setAttribute on a fixed attribute
 *    list. There is no innerHTML, outerHTML, insertAdjacentHTML, document.write, eval, or Function.
 *  - A link from the API is used only when it is an https URL.
 *  - The API key lives in the input field and in memory; it is never stored or put in a URL.
 *  - No request goes anywhere but this origin (the page's content security policy enforces it).
 */
(function () {
  const MAX_DEPTH = 6;
  const statusBox = document.getElementById("status");
  const keyInput = document.getElementById("api-key");
  let lastDossier = null;
  let queueAfter = null;

  // ---- small DOM helpers ---------------------------------------------------------------

  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(props || {})) {
      if (name === "class") node.className = value;
      else if (name === "text") node.textContent = value;
      else node.setAttribute(name, value);
    }
    for (const child of children) {
      if (child === null || child === undefined) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function show(container, ...nodes) {
    clear(container);
    container.append(...nodes);
  }

  function setStatus(message) {
    statusBox.textContent = message || "";
  }

  function safeHttpsUrl(value) {
    try {
      const url = new URL(String(value));
      return url.protocol === "https:" ? url.href : null;
    } catch (_err) {
      return null;
    }
  }

  // ---- API -----------------------------------------------------------------------------

  async function api(path) {
    const headers = { Accept: "application/json" };
    if (keyInput.value) headers["X-API-Key"] = keyInput.value;
    let response;
    try {
      response = await fetch(path, { headers, cache: "no-store", credentials: "omit" });
    } catch (_err) {
      throw new Error("The service could not be reached.");
    }
    let body = null;
    try {
      body = await response.json();
    } catch (_err) {
      body = null;
    }
    if (!response.ok) {
      const title = body && body.title ? body.title : "Request failed";
      const detail = body && body.detail ? body.detail : "";
      const id = body && body.request_id ? " (request " + body.request_id + ")" : "";
      throw new Error(title + ": " + detail + id);
    }
    return body;
  }

  async function guarded(container, work) {
    setStatus("Loading...");
    try {
      await work();
      setStatus("");
    } catch (err) {
      setStatus("");
      show(container, el("div", { class: "card error", role: "alert", text: err.message }));
    }
  }

  // ---- renderers -----------------------------------------------------------------------

  function renderScalar(value) {
    if (value === null || value === undefined) return el("span", { class: "meta", text: "none" });
    return document.createTextNode(String(value));
  }

  function renderData(value, depth) {
    if (depth > MAX_DEPTH) return el("span", { class: "meta", text: "(nested data not shown)" });
    if (Array.isArray(value)) {
      if (value.length === 0) return el("span", { class: "meta", text: "none" });
      if (value.every((v) => v === null || typeof v !== "object")) {
        return document.createTextNode(value.join(", "));
      }
      const list = el("ul", { class: "plain" });
      for (const item of value) list.append(el("li", {}, renderData(item, depth + 1)));
      return list;
    }
    if (value !== null && typeof value === "object") {
      const dl = el("dl");
      for (const [key, inner] of Object.entries(value)) {
        dl.append(el("dt", { text: key }), el("dd", {}, renderData(inner, depth + 1)));
      }
      return dl;
    }
    return renderScalar(value);
  }

  function renderPairs(pairs) {
    const dl = el("dl");
    for (const pair of pairs || []) {
      dl.append(el("dt", { text: pair.name }), el("dd", { text: pair.value }));
    }
    return dl;
  }

  function renderFinding(finding) {
    const card = el("div", { class: "card" });
    card.append(el("strong", { text: finding.summary }), el("span", { class: "badge", text: finding.check }));
    if (finding.detail && finding.detail.length) card.append(renderPairs(finding.detail));
    if (finding.refs && finding.refs.length) {
      const refs = el("p", { class: "meta" }, "Evidence: ");
      finding.refs.forEach((ref, i) => {
        if (i) refs.append(", ");
        refs.append(ref.kind + " " + ref.id);
      });
      card.append(refs);
    }
    return card;
  }

  function renderToolResult(result) {
    const box = el("div", { class: "card" });
    // Anchor for "Open in dossier" links from Ask answers; tool names are fixed lowercase ids.
    if (/^[a-z_]{1,40}$/.test(String(result.tool))) box.id = "check-" + result.tool;
    box.append(el("h3", { text: result.tool + " on " + result.subject }));
    box.append(el("p", { class: "meta", text: "Examined: " + result.examined }));
    if (result.parameters && result.parameters.length) box.append(renderPairs(result.parameters));
    if (!result.findings.length && !result.observations.length) {
      box.append(el("p", { text: "Nothing found by this check." }));
    }
    for (const f of result.findings) box.append(renderFinding(f));
    if (result.observations.length) {
      box.append(el("h3", { text: "Observations (context, not findings)" }));
      for (const o of result.observations) box.append(renderFinding(o));
    }
    if (result.metrics && result.metrics.length) {
      box.append(el("h3", { text: "Metrics" }), renderPairs(result.metrics));
    }
    if (result.limits && result.limits.length) {
      box.append(el("h3", { text: "What this check could not see" }));
      const list = el("ul");
      for (const l of result.limits) list.append(el("li", { text: l }));
      box.append(list);
    }
    box.append(el("p", { class: "hint", text: result.notice }));
    return box;
  }

  function table(headers, rows) {
    const t = el("table");
    const head = el("tr");
    for (const h of headers) head.append(el("th", { scope: "col", text: h }));
    t.append(el("thead", {}, head));
    const body = el("tbody");
    for (const row of rows) {
      const tr = el("tr");
      for (const cell of row) tr.append(el("td", {}, cell));
      body.append(tr);
    }
    t.append(body);
    const wrap = el("div", { class: "table-wrap" });
    wrap.append(t);
    return wrap;
  }

  function linkButton(label, onClick) {
    const b = el("button", { type: "button", class: "link", text: label });
    b.addEventListener("click", onClick);
    return b;
  }

  // ---- views ---------------------------------------------------------------------------

  const views = ["queue", "claim", "entity", "policy", "ask"];
  function switchView(name) {
    for (const v of views) {
      document.querySelector('[data-panel="' + v + '"]').hidden = v !== name;
      const btn = document.querySelector('nav [data-view="' + v + '"]');
      if (v === name) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    }
    setStatus("");
  }

  async function loadQueue(append) {
    const out = document.getElementById("queue-out");
    await guarded(out, async () => {
      const code = document.getElementById("screen-code").value.trim();
      const params = new URLSearchParams({ limit: "50" });
      if (code) params.set("screen_code", code);
      if (append && queueAfter) params.set("after", queueAfter);
      const data = await api("/v1/flags?" + params.toString());
      const rows = data.flags.map((f) => [
        f.flag_id,
        linkButton(f.claim_id, () => openClaim(f.claim_id)),
        f.screen_code,
        f.screen_text,
      ]);
      queueAfter = data.next_after;
      const summary = el("p", { class: "meta", text: data.total + " flags in total; showing " + rows.length + (data.truncated ? " (more available)" : "") });
      const nodes = [summary, table(["Flag", "Claim", "Screen", "What the screen checks"], rows)];
      if (data.truncated && data.next_after) {
        const more = el("button", { type: "button", text: "Load next page" });
        more.addEventListener("click", () => loadQueue(true));
        nodes.push(more);
      }
      show(out, ...nodes);
    });
  }

  async function openClaim(claimId) {
    switchView("claim");
    document.getElementById("claim-id").value = claimId;
    const out = document.getElementById("claim-out");
    const download = document.getElementById("download");
    const askAbout = document.getElementById("ask-about");
    download.hidden = true;
    if (askAbout) askAbout.hidden = true;
    lastDossier = null;
    await guarded(out, async () => {
      const d = await api("/v1/claims/" + encodeURIComponent(claimId) + "/dossier");
      lastDossier = d;
      history.replaceState(null, "", "#claim=" + encodeURIComponent(d.claim.claim_id));
      const c = d.claim;
      const header = el("div", { class: "card" });
      header.append(el("h3", { text: "Claim " + c.claim_id }));
      header.append(
        renderData({
          member: c.member_id,
          provider: c.provider_id,
          service_from: c.service_from,
          service_to: c.service_to,
          place_of_service: c.place_of_service,
          diagnosis_codes: c.diagnosis_codes,
          total_billed: c.total_billed,
        }, 0)
      );
      header.append(
        linkButton("Provider " + c.provider_id, () => openEntity(c.provider_id)),
        document.createTextNode("  "),
        linkButton("Member " + c.member_id, () => openEntity(c.member_id))
      );
      const lineRows = d.lines.map((l) => [
        l.line_no, l.code, (l.modifiers || []).join(" "), l.units, l.billed_amount, l.service_date, l.dx_pointer,
      ]);
      const flags = d.flags.length
        ? table(["Flag", "Screen", "What the screen checks"], d.flags.map((f) => [f.flag_id, f.screen_code, f.screen_text]))
        : el("p", { text: "No screen flagged this claim." });
      show(
        out,
        el("p", { class: "meta", text: d.finding_count + " findings across " + d.results.length + " checks" }),
        header,
        el("h3", { text: "Lines" }),
        table(["Line", "Code", "Modifiers", "Units", "Billed", "Service date", "Dx pointer"], lineRows),
        el("h3", { text: "Flags" }),
        flags,
        el("h2", { text: "Checks" }),
        ...d.results.map(renderToolResult),
        el("p", { class: "hint", text: d.notice })
      );
      download.hidden = false;
      if (askAbout) askAbout.hidden = false;
    });
  }

  async function openEntity(id) {
    switchView("entity");
    document.getElementById("entity-id").value = id;
    const out = document.getElementById("entity-out");
    await guarded(out, async () => {
      const enc = encodeURIComponent(id);
      if (/^P/i.test(id)) {
        const [profile, intensity, peers] = await Promise.all([
          api("/v1/providers/" + enc),
          api("/v1/providers/" + enc + "/intensity"),
          api("/v1/providers/" + enc + "/peers?limit=10"),
        ]);
        show(
          out,
          el("div", { class: "card" }, el("h3", { text: "Provider " + id }), renderData(profile, 0)),
          renderToolResult(intensity),
          el("div", { class: "card" }, el("h3", { text: "Peer group" }), renderData(peers, 0))
        );
      } else {
        const history_ = await api("/v1/members/" + enc + "/history?limit=50");
        show(out, el("div", { class: "card" }, el("h3", { text: "Member " + id }), renderData(history_, 0)));
      }
    });
  }

  // Display only: the stored chunk and the quote check never see this. Rejoins acronyms that
  // PDF extraction split ("H\nCPCS"; A and I are left alone because they are words), rejoins
  // hyphenated line breaks, and turns single line breaks into spaces.
  function cleanForDisplay(text) {
    return String(text)
      .replace(/\b([B-HJ-Z])[ \t]*\n[ \t]*([A-Z]{2,})\b/g, "$1$2")
      .replace(/(\w)-\n(\w)/g, "$1$2")
      .replace(/[ \t]*\n(?!\n)[ \t]*/g, " ")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  const STOP = new Set(["the", "and", "for", "what", "does", "say", "about", "with", "that", "this", "are", "how", "when", "from", "which"]);

  // The one or two adjacent sentences sharing the most search words; falls back to the start.
  function bestPassage(text, query) {
    const words = String(query).toLowerCase().match(/[a-z0-9]{3,}/g) || [];
    const terms = words.filter((w) => !STOP.has(w));
    const sentences = text.split(/(?<=[.;:])\s+/);
    let best = { score: 0, start: 0 };
    sentences.forEach((_, i) => {
      const pair = (sentences[i] + " " + (sentences[i + 1] || "")).toLowerCase();
      const score = terms.filter((t) => pair.includes(t)).length;
      if (score > best.score) best = { score, start: i };
    });
    if (!best.score) return text.length > 320 ? text.slice(0, 320) + "..." : text;
    return sentences.slice(best.start, best.start + 2).join(" ");
  }

  function renderPassage(rawText, query) {
    const text = cleanForDisplay(rawText);
    const passage = bestPassage(text, query);
    const nodes = [el("blockquote", { text: passage })];
    if (passage !== text) {
      nodes.push(
        el("details", { class: "full-text" },
          el("summary", { text: "Show the full passage" }),
          el("blockquote", { text: text }))
      );
    }
    nodes.push(el("p", { class: "micro", text: "Line breaks and split acronyms tidied for display; the stored source text is unchanged." }));
    return nodes;
  }

  async function searchPolicy(query) {
    const out = document.getElementById("policy-out");
    await guarded(out, async () => {
      const params = new URLSearchParams({ q: query, k: "5" });
      const data = await api("/v1/policy/search?" + params.toString());
      const nodes = [
        el("p", { class: "meta", text: "Search mode: " + data.mode + "; ranking: " + data.ranking + "; " + data.indexed_chunks + " passages indexed" }),
      ];
      if (data.fallback_reason) {
        nodes.push(el("div", { class: "card", role: "note", text: "Fell back to keyword search: " + data.fallback_reason }));
      }
      if (!data.hits.length) nodes.push(el("p", { text: "No passage matched. That is not evidence the sources are silent: try other terms." }));
      for (const hit of data.hits) {
        const card = el("div", { class: "card" });
        const url = safeHttpsUrl(hit.source.url);
        const title = url
          ? el("a", { href: url, rel: "noopener noreferrer", target: "_blank", text: hit.source.title })
          : el("span", { text: hit.source.title });
        card.append(
          el("strong", {}, title),
          el("span", { class: "badge untrusted", text: "source text, untrusted" }),
          el("p", { class: "meta", text: "pages " + hit.page_start + " to " + hit.page_end + (hit.section ? " | " + hit.section : "") }),
          ...renderPassage(hit.text, query),
          el("p", { class: "meta", text: "chunk " + hit.chunk_id + " | source " + hit.source.source_id + " | retrieved " + hit.source.retrieved_at + " | sha256 " + hit.source.sha256.slice(0, 16) })
        );
        nodes.push(card);
      }
      nodes.push(el("p", { class: "hint", text: data.notice }));
      show(out, ...nodes);
    });
  }

  // ---- Ask the agent -------------------------------------------------------------------
  // The server sends a view built from the validated answer. Model text appears only as
  // statement text; it is written with textContent like everything else.

  const ask = { session: null, history: [] };
  const STATUS_CLASS = {
    ANSWERED: "answered",
    CONFLICTING_EVIDENCE: "conflict",
    INSUFFICIENT_EVIDENCE: "insufficient",
    OUT_OF_SCOPE: "scope",
    INVALID_OUTPUT: "invalid",
  };
  const fmtUsd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 });

  async function postJson(path, body) {
    const headers = { Accept: "application/json", "Content-Type": "application/json" };
    if (keyInput.value) headers["X-API-Key"] = keyInput.value;
    let response;
    try {
      response = await fetch(path, { method: "POST", headers, body: JSON.stringify(body), cache: "no-store", credentials: "omit" });
    } catch (_err) {
      throw new Error("The service could not be reached.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const title = data && data.title ? data.title : "Request failed";
      throw new Error(title + ": " + (data && data.detail ? data.detail : ""));
    }
    return data;
  }

  function section(title, ...children) {
    return el("section", { class: "ask-section" }, el("h3", { text: title }), ...children);
  }

  function refButton(n) {
    const b = el("button", { type: "button", class: "ref", text: "[" + n + "]", "aria-label": "Source " + n });
    b.addEventListener("click", () => {
      const target = document.getElementById("ask-src-" + n);
      if (target) { target.scrollIntoView({ block: "center" }); target.focus(); }
    });
    return b;
  }

  function statusBadge(view) {
    const kind = STATUS_CLASS[view.status] || "invalid";
    return el("p", { class: "ask-status status-" + kind },
      el("span", { class: "smark", "aria-hidden": "true" }),
      el("strong", { text: view.status_label }),
      el("span", { class: "meta", text: view.status }));
  }

  function renderStatements(view) {
    const list = el("ul", { class: "statements" });
    for (const s of view.statements) {
      const li = el("li", {}, s.text + " ");
      for (const n of s.refs) li.append(refButton(n), " ");
      list.append(li);
    }
    return section("Answer", list);
  }

  async function openCheck(link) {
    if (link.view === "entity") return openEntity(link.id);
    await openClaim(link.id);
    const card = document.getElementById("check-" + link.check);
    if (card) { card.setAttribute("tabindex", "-1"); card.scrollIntoView({ block: "start" }); card.focus(); }
  }

  function renderEvidenceItem(src) {
    const item = el("li", { class: "card src", id: "ask-src-" + src.n, tabindex: "-1" });
    item.append(el("p", {}, el("span", { class: "ref-label", text: "[" + src.n + "]" }), " ", el("strong", { text: src.label })));
    item.append(el("p", { class: "meta", text: src.id + " | " + src.tool + (src.subject ? " on " + src.subject : "") + (src.check_status ? " | " + src.check_status : "") }));
    if (src.examined) item.append(el("p", { class: "hint", text: "Examined: " + src.examined }));
    if (src.limits && src.limits.length) {
      const list = el("ul", { class: "hint" });
      for (const l of src.limits) list.append(el("li", { text: l }));
      item.append(el("p", { class: "hint", text: "What this check could not see:" }), list);
    }
    if (src.link) {
      const label = src.link.view === "entity" ? "Open " + src.link.id : "Open in dossier";
      item.append(linkButton(label, () => openCheck(src.link)));
    }
    return item;
  }

  function renderPolicyItem(src) {
    const item = el("li", { class: "card src", id: "ask-src-" + src.n, tabindex: "-1" });
    const url = safeHttpsUrl(src.url);
    const title = url ? el("a", { href: url, rel: "noopener noreferrer", target: "_blank", text: src.title }) : el("span", { text: src.title });
    item.append(el("p", {}, el("span", { class: "ref-label", text: "[" + src.n + "]" }), " ", el("strong", {}, title),
      el("span", { class: "badge untrusted", text: "source text, untrusted" })));
    item.append(el("p", { class: "meta", text: "pages " + src.page_start + " to " + src.page_end + (src.section ? " | " + src.section : "") + " | chunk " + src.id }));
    item.append(el("p", { class: "meta", text: "source " + src.source_id + " | retrieved " + src.retrieved_at + " | sha256 " + String(src.sha256).slice(0, 16) }));
    if (src.quotes.length) {
      for (const q of src.quotes) item.append(el("blockquote", { text: q }));
    } else {
      item.append(el("p", { class: "hint", text: "Cited, not quoted." }));
    }
    item.append(el("details", { class: "full-text" }, el("summary", { text: "Show the full passage" }), el("blockquote", { text: cleanForDisplay(src.text) })));
    return item;
  }

  function renderSearchItem(src) {
    return el("li", { class: "card src", id: "ask-src-" + src.n, tabindex: "-1" },
      el("span", { class: "ref-label", text: "[" + src.n + "]" }), " ", el("span", { text: src.label }));
  }

  function renderRunDetails(view) {
    const r = view.run || {};
    const rows = view.tools.map((t) => [t.tool, el("code", { text: t.arguments }),
      t.is_error ? "error" : ("shown" in t ? t.shown + " shown, " + t.withheld + " withheld (" + t.mode + (t.relevance_checked ? "" : ", relevance check off") + ")" : "ok")]);
    return el("details", { class: "run-details" },
      el("summary", { text: "Run details" }),
      renderPairs([
        { name: "Provider / model", value: r.provider + " / " + r.model + " (" + r.prompt_version + ")" },
        { name: "Model turns", value: String(r.model_turns) },
        { name: "Tool calls", value: String(r.tool_calls) },
        { name: "Cost this question", value: fmtUsd.format(Number(r.turn_cost_usd)) + " (model " + fmtUsd.format(Number(r.model_cost_usd)) + ", rest is search)" },
        { name: "Elapsed", value: r.elapsed_s + " s" },
        { name: "Stopped by", value: r.limit || "the model's final answer" },
        { name: "Run id", value: r.run_id },
      ]),
      rows.length ? table(["Tool", "Arguments (as the model sent them)", "Result"], rows) : el("p", { class: "hint", text: "No tool was called." }));
  }

  function renderAsk(view) {
    const nodes = [statusBadge(view)];
    if (view.message) nodes.push(el("p", { class: "ask-message", text: view.message }));
    if (view.reason_text && view.status !== "ANSWERED") nodes.push(el("p", { class: "hint", text: view.reason_text }));
    if (view.statements.length) nodes.push(renderStatements(view));
    const evidence = view.sources.filter((s) => s.kind !== "policy" && s.kind !== "search");
    const policy = view.sources.filter((s) => s.kind === "policy" || s.kind === "search");
    if (evidence.length) nodes.push(section("What the claim data shows", el("ul", { class: "plain" }, ...evidence.map(renderEvidenceItem))));
    if (policy.length) nodes.push(section("What the policy sources say", el("ul", { class: "plain" }, ...policy.map((s) => (s.kind === "policy" ? renderPolicyItem(s) : renderSearchItem(s))))));
    if (view.searched.length) {
      const list = el("ul", { class: "hint" });
      for (const s of view.searched) list.append(el("li", {}, el("code", { text: s })));
      nodes.push(section("What was searched", list));
    }
    if (view.suggestions.length) {
      const chips = el("div", { class: "examples" });
      for (const q of view.suggestions) chips.append(fillChip(q));
      nodes.push(section(view.status === "OUT_OF_SCOPE" ? "Evidence questions you can ask instead" : "Suggestion", chips));
    }
    if (view.limits.length) {
      const list = el("ul");
      for (const l of view.limits) list.append(el("li", { text: l }));
      nodes.push(section("Limits and open points", list));
    }
    if (view.run) nodes.push(renderRunDetails(view));
    return nodes;
  }

  // Suggestions fill the question box; they never send it (each question costs money).
  function fillChip(text) {
    const b = el("button", { type: "button", class: "chip suggestion", text: text });
    b.addEventListener("click", () => { const q = document.getElementById("ask-q"); q.value = text; q.focus(); });
    return b;
  }

  function renderSessionLine(session) {
    const line = document.getElementById("ask-session");
    if (!session) { line.textContent = "New session. Claim in scope: none."; return; }
    line.textContent = (session.renewed ? "Your earlier session had expired; this is a new one. " : "") +
      "Session question " + session.turn + ". Claim in scope: " + (session.claim_id || "none") +
      ". Session spend " + fmtUsd.format(Number(session.spent_usd)) + " of " + fmtUsd.format(Number(session.ceiling_usd)) + ".";
    if (session.claim_id) document.getElementById("ask-claim").value = session.claim_id;
  }

  function renderHistory() {
    const list = document.getElementById("ask-history");
    list.replaceChildren(...ask.history.slice(0, -1).map((h) => el("li", {}, el("span", { class: "meta", text: h.status }), " ", h.question)));
  }

  async function askQuestion() {
    const q = document.getElementById("ask-q").value.trim();
    const claim = document.getElementById("ask-claim").value.trim().toUpperCase();
    if (!q) return;
    const out = document.getElementById("ask-out");
    const submit = document.getElementById("ask-submit");
    submit.disabled = true;
    setStatus("Searching the claims data and the public sources... this can take 10 to 40 seconds.");
    try {
      const body = { question: q };
      if (claim) body.claim_id = claim;
      if (ask.session) body.session = ask.session;
      const view = await postJson("/workbench/ask", body);
      ask.session = view.session.token;
      ask.history.push({ question: q, status: view.status });
      renderSessionLine(view.session);
      renderHistory();
      show(out, ...renderAsk(view));
      setStatus("");
    } catch (err) {
      setStatus("");
      show(out, el("div", { class: "card error", role: "alert", text: err.message }));
    } finally {
      submit.disabled = false;
    }
  }

  async function newSession() {
    if (ask.session) {
      try { await postJson("/workbench/ask/reset", { session: ask.session }); } catch (_err) { /* the session expires on its own */ }
    }
    ask.session = null;
    ask.history = [];
    renderHistory();
    renderSessionLine(null);
    document.getElementById("ask-claim").value = "";
    clear(document.getElementById("ask-out"));
  }

  async function loadAskStatus() {
    const off = document.getElementById("ask-off");
    if (!off) return;
    try {
      const s = await api("/workbench/ask/status");
      off.hidden = !!s.enabled;
      off.textContent = s.enabled ? "" : s.note;
      document.getElementById("ask-submit").disabled = !s.enabled;
      if (s.enabled && !s.policy_search) {
        off.hidden = false;
        off.textContent = "Policy search is in keyword mode on this server (" + s.policy_search_note + "); passages are not checked for relevance.";
      }
    } catch (err) {
      off.hidden = false;
      off.textContent = err.message;
    }
  }

  function downloadDossier() {
    if (!lastDossier) return;
    const blob = new Blob([JSON.stringify(lastDossier, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: "evidence-" + lastDossier.claim.claim_id + ".json" });
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function checkHealth() {
    const box = document.getElementById("health");
    try {
      const h = await fetch("/v1/health", { cache: "no-store", credentials: "omit" }).then((r) => r.json());
      box.textContent = "service " + h.status + " \u00b7 " + h.claim_count + " claims" + (h.policy_search ? "" : " \u00b7 policy search off");
    } catch (_err) {
      box.textContent = "service not reachable";
    }
  }

  // ---- wiring --------------------------------------------------------------------------

  for (const btn of document.querySelectorAll("nav [data-view]")) {
    btn.addEventListener("click", () => switchView(btn.getAttribute("data-view")));
  }
  document.getElementById("queue-form").addEventListener("submit", (e) => {
    e.preventDefault();
    queueAfter = null;
    loadQueue(false);
  });
  document.getElementById("claim-form").addEventListener("submit", (e) => {
    e.preventDefault();
    openClaim(document.getElementById("claim-id").value.trim());
  });
  document.getElementById("entity-form").addEventListener("submit", (e) => {
    e.preventDefault();
    openEntity(document.getElementById("entity-id").value.trim());
  });
  document.getElementById("policy-form").addEventListener("submit", (e) => {
    e.preventDefault();
    searchPolicy(document.getElementById("policy-q").value.trim());
  });
  document.getElementById("download").addEventListener("click", downloadDossier);
  // Ask controls are wired only when present, like the example chips below.
  function on(id, type, handler) {
    const node = document.getElementById(id);
    if (node) node.addEventListener(type, handler);
  }
  on("ask-form", "submit", (e) => {
    e.preventDefault();
    askQuestion();
  });
  on("ask-new", "click", newSession);
  on("ask-about", "click", () => {
    switchView("ask");
    if (lastDossier) document.getElementById("ask-claim").value = lastDossier.claim.claim_id;
    document.getElementById("ask-q").focus();
  });
  // Ask examples fill the form only; sending is always the investigator's click.
  const askExamples = {
    "ex-ask-1": ["Why would two codes billed on the same day without a modifier be flagged, and what do the policy sources say?", "C0000493"],
    "ex-ask-2": ["What about the unit limit on that claim?", ""],
    "ex-ask-3": ["What do the policy sources say about helicopter transport authorization?", ""],
    "ex-ask-4": ["Compare provider P0011 with its peers and tell me the limits.", ""],
  };
  for (const [id, [question, claim]] of Object.entries(askExamples)) {
    wireExample(id, () => {
      document.getElementById("ask-q").value = question;
      if (claim) document.getElementById("ask-claim").value = claim;
      document.getElementById("ask-q").focus();
    });
  }

  // Example chips fill and run the real forms with synthetic example ids. Elements are
  // looked up one by one and skipped when absent, so a partial page still works.
  function wireExample(id, run) {
    const chip = document.getElementById(id);
    if (chip) chip.addEventListener("click", run);
  }
  wireExample("ex-screen", () => {
    document.getElementById("screen-code").value = "SCR01";
    queueAfter = null;
    loadQueue(false);
  });
  wireExample("ex-claim", () => openClaim("C0000001"));
  wireExample("ex-provider", () => openEntity("P0001"));
  wireExample("ex-member", () => openEntity("M000001"));
  wireExample("ex-policy", () => {
    document.getElementById("policy-q").value = "modifier";
    searchPolicy("modifier");
  });

  // A typed hint cycles real search terms in the policy box. It never runs a search, stops
  // as soon as the investigator touches the box, and stays off when reduced motion is asked
  // for (or when the environment cannot report that preference, e.g. the fake-DOM tests).
  const policyInput = document.getElementById("policy-q");
  if (
    policyInput &&
    typeof window.matchMedia === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    const hints = ["modifier", "place of service", "duplicate", "units"];
    let hintIndex = 0;
    let charIndex = 0;
    let stopped = false;
    policyInput.addEventListener("focus", () => { stopped = true; });
    policyInput.addEventListener("input", () => { stopped = true; });
    const tickHint = () => {
      if (stopped || policyInput.value) return;
      const word = hints[hintIndex % hints.length];
      charIndex += 1;
      if (charIndex > word.length + 14) {
        hintIndex += 1;
        charIndex = 0;
      }
      policyInput.setAttribute("placeholder", "Try: " + word.slice(0, Math.min(charIndex, word.length)));
      setTimeout(tickHint, charIndex === 0 ? 350 : 85);
    };
    tickHint();
  }

  checkHealth();
  loadAskStatus();
  const fromHash = /^#claim=(C\d{7})$/.exec(location.hash);
  if (fromHash) openClaim(fromHash[1]);
  else if (location.hash === "#ask") switchView("ask");
})();
