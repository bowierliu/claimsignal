"use strict";
/*
 * Read-only evidence viewer over the /v1 API.
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
    return t;
  }

  function linkButton(label, onClick) {
    const b = el("button", { type: "button", class: "link", text: label });
    b.addEventListener("click", onClick);
    return b;
  }

  // ---- views ---------------------------------------------------------------------------

  const views = ["queue", "claim", "entity", "policy"];
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
    download.hidden = true;
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
          el("blockquote", { text: hit.text }),
          el("p", { class: "meta", text: "chunk " + hit.chunk_id + " | source " + hit.source.source_id + " | retrieved " + hit.source.retrieved_at + " | sha256 " + hit.source.sha256.slice(0, 16) })
        );
        nodes.push(card);
      }
      nodes.push(el("p", { class: "hint", text: data.notice }));
      show(out, ...nodes);
    });
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
      box.textContent = "service " + h.status + "; " + h.claim_count + " claims; policy search " + (h.policy_search ? "on" : "off");
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

  checkHealth();
  const fromHash = /^#claim=(C\d{7})$/.exec(location.hash);
  if (fromHash) openClaim(fromHash[1]);
})();
