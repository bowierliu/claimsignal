"use strict";
const byId = (id) => document.getElementById(id);
const local = location.origin === "http://127.0.0.1:8763";
let selected = "units";
let pending = false;
let revision = 0;
function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}
function render(key, data, live = false) {
  const info = REPLAY.cases[key];
  const {dossier, result} = data;
  byId("claim").textContent = "Synthetic claim · " + dossier.claim;
  byId("question").textContent = info.question;
  if (local) byId("ask").href = "/workbench#ask=" + dossier.claim;
  byId("mode").textContent = live ? "Live model selection" : "Offline replay";
  byId("window").textContent = "Service window · " + dossier.window.join(" to ");
  byId("lines").replaceChildren(...dossier.lines.map(line => {
    const row = document.createElement("tr");
    for (const text of [line.id, line.code, line.units, line.date, line.modifiers.join(", ") || "None"]) {
      row.append(element("td", text));
    }
    return row;
  }));
  byId("evidence").replaceChildren(...result.evidence.map(item => {
    const box = element("div", "", "finding");
    const refs = element("div", "", "refs");
    for (const ref of item.refs) refs.append(element("span", ref.kind + " · " + ref.id, "ref"));
    box.append(element("p", item.text), refs);
    return box;
  }));
  byId("scope").textContent = result.limits.join(" ");
  const trace = live
    ? ["Read the synthetic dossier.", "OpenAI selected " + result.tool + ".",
       "Ran the selected check against the synthetic database.",
       "Validated the model-selected evidence ID against the tool output. Displayed its original wording."]
    : ["Opened the saved output for " + dossier.claim + ".",
       "Replayed " + result.tool + " from the repository’s deterministic checks.",
       "Displayed the saved evidence and source identifiers. This replay calls no model."];
  byId("steps").replaceChildren(...trace.map(text => element("li", text)));
  for (const button of byId("cases").children) {
    button.setAttribute("aria-pressed", String(button.dataset.key === key));
  }
}
function openCase(key) {
  selected = key;
  revision += 1;
  byId("trace").open = false;
  byId("live-status").textContent = "";
  render(key, REPLAY.cases[key]);
}
document.title = REPLAY.name + " · Claims investigation";
byId("brand").textContent = REPLAY.name;
for (const [key, info] of Object.entries(REPLAY.cases)) {
  const button = element("button", "", "case");
  button.type = "button";
  button.dataset.key = key;
  button.append(element("strong", info.title), element("span", info.dossier.claim));
  button.addEventListener("click", () => openCase(key));
  byId("cases").append(button);
}
openCase(selected);
if (local) {
  byId("live-run").hidden = false;
  byId("ask").hidden = false;
  byId("live-note").textContent = "OpenAI will choose a check and select evidence using your server-side key. This run may incur a small charge.";
}
byId("live-run").addEventListener("click", async () => {
  if (!local || pending) return;
  const key = selected, current = ++revision;
  pending = true;
  byId("live-run").disabled = true;
  // Retain an explicitly labelled offline case if the live request fails.
  render(key, REPLAY.cases[key]);
  byId("live-status").textContent = "Running model-assisted investigation…";
  try {
    const response = await fetch("/api/investigations/" + key, {
      method: "POST", headers: {"X-Demo-Request": "investigate"}, cache: "no-store",
      credentials: "omit", redirect: "error"
    });
    const data = await response.json();
    if (current !== revision) return;
    if (!response.ok) {
      byId("live-status").textContent = data.error || "The live investigation could not finish.";
      return;
    }
    if (data.mode !== "live") throw new Error("Unexpected response");
    render(key, data, true);
    byId("live-status").textContent = "Live investigation complete.";
  } catch {
    if (current === revision) byId("live-status").textContent = "The local service is unavailable. Open the launcher and try again.";
  } finally {
    pending = false;
    byId("live-run").disabled = false;
  }
});
