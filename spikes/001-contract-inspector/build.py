"""Build a self-contained HTML inspector from checked-in tool contracts."""

from __future__ import annotations

import json
from pathlib import Path


SPIKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SPIKE_DIR.parents[1]
CONTRACT_GLOB = "contracts/tools/*/*.json"
OUTPUT_PATH = SPIKE_DIR / "contract-inspector.html"


def load_contracts() -> list[dict]:
    """Load contract instances in stable tool/version order."""
    contracts = [json.loads(path.read_text(encoding="utf-8")) for path in REPO_ROOT.glob(CONTRACT_GLOB)]
    return sorted(contracts, key=lambda item: (item["toolId"], item["version"]))


def build() -> Path:
    """Render all public contract data into a portable HTML artifact."""
    contract_json = json.dumps(load_contracts(), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__CONTRACT_DATA__", contract_json)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    return OUTPUT_PATH


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tool Contract Inspector</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0f10;
      --rail: #0f1415;
      --panel: #131a1b;
      --panel-2: #182122;
      --line: #2a3638;
      --line-strong: #3a494b;
      --ink: #f2f0e8;
      --muted: #9aa8a8;
      --dim: #6f7d7d;
      --amber: #e8b45a;
      --cyan: #79c9c4;
      --green: #86c98a;
      --red: #e18478;
      --mono: "Cascadia Code", "IBM Plex Mono", "Liberation Mono", monospace;
      --sans: "Trebuchet MS", "Avenir Next", Arial, sans-serif;
    }

    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.5 var(--sans);
    }
    button, input { font: inherit; }
    button { color: inherit; }
    :focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }

    .shell {
      display: grid;
      grid-template-columns: 310px minmax(0, 1fr);
      min-height: 100vh;
    }
    .rail {
      position: sticky;
      top: 0;
      min-width: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      background: var(--rail);
      border-right: 1px solid var(--line);
      padding: 24px 18px;
    }
    .brand { padding: 0 8px 22px; }
    .eyebrow {
      margin: 0 0 6px;
      color: var(--amber);
      font: 700 11px/1.2 var(--mono);
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    h1 { margin: 0; font-size: 21px; line-height: 1.15; letter-spacing: -.02em; }
    .brand p { margin: 8px 0 0; color: var(--muted); font-size: 13px; }
    .search {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #0a0e0f;
      color: var(--ink);
      padding: 0 12px;
    }
    .search::placeholder { color: var(--dim); }
    .contract-list {
      display: grid;
      gap: 7px;
      margin-top: 14px;
      overflow: auto;
      padding: 2px 2px 14px;
    }
    .contract-button {
      width: 100%;
      border: 1px solid transparent;
      border-radius: 7px;
      background: transparent;
      padding: 12px;
      text-align: left;
      cursor: pointer;
    }
    .contract-button:hover { background: var(--panel); border-color: var(--line); }
    .contract-button.active { background: var(--panel-2); border-color: var(--line-strong); }
    .contract-id { display: block; font: 700 12px/1.35 var(--mono); color: var(--ink); }
    .contract-name { display: block; margin-top: 5px; color: var(--muted); font-size: 12px; }
    .rail-footer {
      margin-top: auto;
      border-top: 1px solid var(--line);
      padding: 15px 8px 0;
      color: var(--dim);
      font-size: 12px;
    }

    main { min-width: 0; padding: 34px clamp(24px, 5vw, 72px) 70px; }
    .contract-header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: start;
      border-bottom: 1px solid var(--line);
      padding-bottom: 25px;
    }
    .identity { min-width: 0; }
    .identity h2 {
      overflow-wrap: anywhere;
      margin: 5px 0 6px;
      font: 700 clamp(24px, 3vw, 36px)/1.15 var(--mono);
      letter-spacing: -.045em;
    }
    .runtime-name { color: var(--muted); font: 13px/1.4 var(--mono); }
    .version-block { text-align: right; }
    .version-block strong { display: block; font: 700 20px/1 var(--mono); }
    .version-block span { color: var(--dim); font-size: 12px; }
    .description {
      max-width: 880px;
      margin: 22px 0 0;
      color: #d5d9d5;
      font-size: 16px;
      white-space: pre-line;
    }

    .tabs {
      display: flex;
      gap: 4px;
      margin: 28px 0 22px;
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }
    .tab {
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--muted);
      min-height: 44px;
      padding: 0 14px;
      cursor: pointer;
      white-space: nowrap;
    }
    .tab:hover { color: var(--ink); }
    .tab.active { color: var(--ink); border-bottom-color: var(--amber); }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 9px;
      padding: 20px;
    }
    .section.wide { grid-column: 1 / -1; }
    .section h3 {
      margin: 0 0 15px;
      color: var(--muted);
      font: 700 11px/1.2 var(--mono);
      letter-spacing: .11em;
      text-transform: uppercase;
    }
    .facts { display: grid; gap: 1px; margin: 0; }
    .fact {
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      gap: 16px;
      padding: 10px 0;
      border-bottom: 1px solid #222c2e;
    }
    .fact:last-child { border-bottom: 0; }
    .fact dt { color: var(--muted); }
    .fact dd { margin: 0; font-family: var(--mono); overflow-wrap: anywhere; }
    .explain { display: block; margin-top: 3px; color: var(--dim); font: 12px/1.45 var(--sans); }
    .badge-row { display: flex; flex-wrap: wrap; gap: 7px; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 27px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      padding: 3px 9px;
      color: #d6dddd;
      background: #101617;
      font: 12px/1.1 var(--mono);
    }
    .badge.trusted { border-color: #3e6744; color: var(--green); }
    .badge.untrusted { border-color: #695b38; color: var(--amber); }
    .badge.effect { border-color: #315f61; color: var(--cyan); }
    .badge.failure { border-color: #69433e; color: #e9a297; }

    .schema-stack { display: grid; gap: 13px; }
    .schema-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }
    .schema-card > header {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: baseline;
      padding: 15px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .schema-card h3 { margin: 0; font: 700 15px/1.25 var(--mono); }
    .variant.success h3 { color: var(--green); }
    .variant.failure h3 { color: var(--red); }
    .path { color: var(--dim); font: 11px/1.3 var(--mono); overflow-wrap: anywhere; }
    .field-list { display: grid; }
    .field {
      display: grid;
      grid-template-columns: minmax(160px, .7fr) minmax(220px, 1.3fr);
      gap: 22px;
      padding: 15px 18px;
      border-bottom: 1px solid #222c2e;
    }
    .field:last-child { border-bottom: 0; }
    .field-name { font: 700 13px/1.4 var(--mono); overflow-wrap: anywhere; }
    .required { margin-left: 7px; color: var(--amber); font-size: 10px; text-transform: uppercase; }
    .type { color: var(--cyan); font: 12px/1.4 var(--mono); }
    .field-description { margin-top: 4px; color: var(--muted); font-size: 13px; }
    .constraint-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .constraint {
      padding: 3px 7px;
      border-radius: 4px;
      background: #0d1213;
      color: #bbc5c5;
      font: 11px/1.3 var(--mono);
    }
    .nested { margin-top: 12px; border-left: 2px solid var(--line-strong); padding-left: 12px; }
    .empty { padding: 30px; text-align: center; color: var(--muted); }

    pre {
      margin: 0;
      max-height: 68vh;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #080c0d;
      padding: 20px;
      color: #d8dfdc;
      font: 12px/1.65 var(--mono);
      tab-size: 2;
    }
    .raw-toolbar { display: flex; justify-content: flex-end; margin-bottom: 10px; }
    .copy-button {
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: var(--panel);
      padding: 0 12px;
      cursor: pointer;
    }
    .copy-button:hover { border-color: var(--amber); }

    .glossary { margin-top: 14px; }
    .glossary details { border-top: 1px solid var(--line); }
    .glossary details:last-child { border-bottom: 1px solid var(--line); }
    .glossary summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; font-family: var(--mono); }
    .glossary p { margin: 0 0 16px; color: var(--muted); max-width: 820px; }

    @media (max-width: 820px) {
      .shell { grid-template-columns: 1fr; }
      .rail { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); padding: 18px; }
      .brand { padding-bottom: 14px; }
      .contract-list { grid-template-columns: repeat(3, minmax(210px, 1fr)); overflow-x: auto; }
      .rail-footer { display: none; }
      main { padding: 26px 18px 50px; }
      .summary-grid { grid-template-columns: 1fr; }
      .section.wide { grid-column: auto; }
      .field { grid-template-columns: 1fr; gap: 7px; }
    }
    @media (max-width: 520px) {
      .contract-header { grid-template-columns: 1fr; }
      .version-block { text-align: left; }
      .fact { grid-template-columns: 1fr; gap: 3px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <p class="eyebrow">AgentCore Evals</p>
        <h1>Tool Contract Inspector</h1>
        <p>Human-readable views generated from the checked-in JSON source.</p>
      </div>
      <label>
        <span class="eyebrow">Find a tool</span>
        <input id="search" class="search" type="search" placeholder="weather, search, calculator…" autocomplete="off">
      </label>
      <nav id="contract-list" class="contract-list" aria-label="Tool contracts"></nav>
      <div class="rail-footer"><span id="contract-count"></span> exact-version contracts · read-only spike</div>
    </aside>

    <main>
      <header class="contract-header">
        <div class="identity">
          <p class="eyebrow">Stable contract identity</p>
          <h2 id="tool-id"></h2>
          <div class="runtime-name">model calls <span id="runtime-name"></span></div>
          <p id="description" class="description"></p>
        </div>
        <div class="version-block">
          <strong id="version"></strong>
          <span>exact behavior version</span>
        </div>
      </header>

      <div class="tabs" role="tablist" aria-label="Contract views">
        <button class="tab active" data-tab="overview" role="tab">Overview</button>
        <button class="tab" data-tab="inputs" role="tab">Inputs</button>
        <button class="tab" data-tab="outputs" role="tab">Outputs</button>
        <button class="tab" data-tab="raw" role="tab">Raw JSON</button>
        <button class="tab" data-tab="glossary" role="tab">Field guide</button>
      </div>
      <section id="view" aria-live="polite"></section>
    </main>
  </div>

  <script>
    const contracts = __CONTRACT_DATA__;
    const glossary = {
      toolId: "Stable namespaced identity used by manifests, datasets, traces, labels, and policy artifacts. It is not the runtime function name.",
      name: "Exact final name exposed to the model after decorators, wrappers, and Gateway transformations.",
      version: "Exact SemVer behavior identity. Consumers pin this value rather than accepting a range.",
      inputSchema: "Arguments the model is allowed to send after the final runtime seam is constructed.",
      outputSchema: "Normalized result visible to the agent—not raw provider, Lambda, Gateway, or MCP transport payloads.",
      failureModes: "Closed set of normalized failure kinds this tool may return.",
      sideEffects: "Highest external effect the tool can produce: none, read_external, or write_external.",
      resultTrust: "Whether returned content is trusted structured data or untrusted external content requiring defensive handling.",
      authScope: "Application-owned authorization label for the execution seam; not an AWS IAM action.",
      latencyBudgetMs: "Maximum expected tool latency in milliseconds for this contract version."
    };

    let selectedIndex = 0;
    let activeTab = "overview";

    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

    function currentContract() { return contracts[selectedIndex]; }

    function syncHash() {
      const c = currentContract();
      history.replaceState(null, "", `#${encodeURIComponent(c.toolId)}@${encodeURIComponent(c.version)}/${activeTab}`);
    }

    function loadHash() {
      const match = location.hash.match(/^#(.+)@([^/]+)\/(.+)$/);
      if (!match) return;
      const toolId = decodeURIComponent(match[1]);
      const version = decodeURIComponent(match[2]);
      const index = contracts.findIndex(c => c.toolId === toolId && c.version === version);
      if (index >= 0) selectedIndex = index;
      if (["overview", "inputs", "outputs", "raw", "glossary"].includes(match[3])) activeTab = match[3];
    }

    function normalizeSearch(value) {
      return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, " ");
    }

    function renderList(filter = "") {
      const normalized = normalizeSearch(filter);
      const list = $("#contract-list");
      list.innerHTML = "";
      contracts.forEach((contract, index) => {
        const haystack = normalizeSearch(`${contract.toolId} ${contract.name} ${contract.description}`);
        if (normalized && !haystack.includes(normalized)) return;
        const button = document.createElement("button");
        button.className = `contract-button${index === selectedIndex ? " active" : ""}`;
        button.innerHTML = `<span class="contract-id">${escapeHtml(contract.toolId)}@${escapeHtml(contract.version)}</span><span class="contract-name">runtime: ${escapeHtml(contract.name)}</span>`;
        button.addEventListener("click", () => {
          selectedIndex = index;
          renderList($("#search").value);
          renderContract();
        });
        list.appendChild(button);
      });
    }

    function badge(value, className = "") {
      return `<span class="badge ${className}">${escapeHtml(value)}</span>`;
    }

    function overview(contract) {
      const trustClass = contract.resultTrust.includes("untrusted") ? "untrusted" : "trusted";
      return `
        <div class="summary-grid">
          <section class="section">
            <h3>Identity</h3>
            <dl class="facts">
              <div class="fact"><dt>toolId</dt><dd>${escapeHtml(contract.toolId)}<span class="explain">Stable join key across artifacts</span></dd></div>
              <div class="fact"><dt>runtime name</dt><dd>${escapeHtml(contract.name)}<span class="explain">Exact name exposed to the model</span></dd></div>
              <div class="fact"><dt>version</dt><dd>${escapeHtml(contract.version)}<span class="explain">Consumers pin this exact behavior</span></dd></div>
            </dl>
          </section>
          <section class="section">
            <h3>Operational envelope</h3>
            <dl class="facts">
              <div class="fact"><dt>side effects</dt><dd>${badge(contract.sideEffects, "effect")}</dd></div>
              <div class="fact"><dt>result trust</dt><dd>${badge(contract.resultTrust, trustClass)}</dd></div>
              <div class="fact"><dt>latency budget</dt><dd>${escapeHtml(contract.latencyBudgetMs)} ms</dd></div>
              <div class="fact"><dt>auth scope</dt><dd>${escapeHtml(contract.authScope || "none")}</dd></div>
            </dl>
          </section>
          <section class="section wide">
            <h3>Normalized failure modes</h3>
            <div class="badge-row">${contract.failureModes.map(mode => badge(mode, "failure")).join("")}</div>
          </section>
          <section class="section wide">
            <h3>At a glance</h3>
            <dl class="facts">
              <div class="fact"><dt>inputs</dt><dd>${Object.keys(contract.inputSchema.properties || {}).length} fields · ${(contract.inputSchema.required || []).length} required</dd></div>
              <div class="fact"><dt>outputs</dt><dd>${contract.outputSchema.oneOf ? `${contract.outputSchema.oneOf.length} normalized variants` : "single schema"}</dd></div>
              <div class="fact"><dt>contract boundary</dt><dd>model-visible spec + normalized result<span class="explain">Raw provider and transport payloads stay behind adapters</span></dd></div>
            </dl>
          </section>
        </div>`;
    }

    function schemaType(schema) {
      if (schema.const !== undefined) return `const ${JSON.stringify(schema.const)}`;
      if (schema.enum) return schema.type || "enum";
      if (schema.oneOf) return "oneOf";
      return schema.type || "schema";
    }

    function constraints(schema) {
      const result = [];
      if (schema.default !== undefined) result.push(`default ${JSON.stringify(schema.default)}`);
      if (schema.enum) result.push(`enum ${schema.enum.map(String).join(" · ")}`);
      if (schema.const !== undefined) result.push(`const ${JSON.stringify(schema.const)}`);
      if (schema.minimum !== undefined) result.push(`min ${schema.minimum}`);
      if (schema.maximum !== undefined) result.push(`max ${schema.maximum}`);
      if (schema.minLength !== undefined) result.push(`min length ${schema.minLength}`);
      if (schema.format) result.push(`format ${schema.format}`);
      if (schema.additionalProperties === false) result.push("closed object");
      return result;
    }

    function fieldsMarkup(schema, path) {
      const properties = schema.properties || {};
      const required = new Set(schema.required || []);
      const entries = Object.entries(properties);
      if (!entries.length) return `<div class="empty">No named fields in this schema.</div>`;
      return `<div class="field-list">${entries.map(([name, child]) => {
        const childPath = `${path}.${name}`;
        const chips = constraints(child).map(item => `<span class="constraint">${escapeHtml(item)}</span>`).join("");
        const nested = child.properties ? `<div class="nested">${fieldsMarkup(child, childPath)}</div>` :
          child.items?.properties ? `<div class="nested"><div class="path">each array item</div>${fieldsMarkup(child.items, `${childPath}[]`)}</div>` : "";
        return `<article class="field">
          <div><div class="field-name">${escapeHtml(name)}${required.has(name) ? '<span class="required">required</span>' : ""}</div><div class="path">${escapeHtml(childPath)}</div></div>
          <div><div class="type">${escapeHtml(schemaType(child))}</div>${child.description ? `<div class="field-description">${escapeHtml(child.description)}</div>` : ""}${chips ? `<div class="constraint-row">${chips}</div>` : ""}${nested}</div>
        </article>`;
      }).join("")}</div>`;
    }

    function schemaCard(title, schema, path, variant = "") {
      return `<section class="schema-card ${variant}"><header><h3>${escapeHtml(title)}</h3><span class="path">${escapeHtml(path)}</span></header>${fieldsMarkup(schema, path)}</section>`;
    }

    function inputView(contract) {
      return `<div class="schema-stack">${schemaCard("Arguments the model may send", contract.inputSchema, "input")}</div>`;
    }

    function outputView(contract) {
      const variants = contract.outputSchema.oneOf || [contract.outputSchema];
      return `<div class="schema-stack">${variants.map((schema, index) => {
        const okConst = schema.properties?.ok?.const;
        const title = okConst === true ? "Success envelope" : okConst === false ? "Failure envelope" : `Variant ${index + 1}`;
        const variant = okConst === true ? "variant success" : okConst === false ? "variant failure" : "variant";
        return schemaCard(title, schema, `output.oneOf[${index}]`, variant);
      }).join("")}</div>`;
    }

    function rawView(contract) {
      return `<div class="raw-toolbar"><button class="copy-button" id="copy-json">Copy JSON</button></div><pre>${escapeHtml(JSON.stringify(contract, null, 2))}</pre>`;
    }

    function glossaryView() {
      return `<section class="section"><h3>Contract field guide</h3><div class="glossary">${Object.entries(glossary).map(([key, text]) => `<details><summary>${escapeHtml(key)}</summary><p>${escapeHtml(text)}</p></details>`).join("")}</div></section>`;
    }

    function renderContract() {
      const contract = currentContract();
      $("#tool-id").textContent = contract.toolId;
      $("#runtime-name").textContent = contract.name;
      $("#version").textContent = `v${contract.version}`;
      $("#description").textContent = contract.description;
      document.querySelectorAll(".tab").forEach(tab => {
        const selected = tab.dataset.tab === activeTab;
        tab.classList.toggle("active", selected);
        tab.setAttribute("aria-selected", selected ? "true" : "false");
      });
      const views = { overview, inputs: inputView, outputs: outputView, raw: rawView, glossary: glossaryView };
      $("#view").innerHTML = views[activeTab](contract);
      if (activeTab === "raw") {
        $("#copy-json").addEventListener("click", async event => {
          await navigator.clipboard.writeText(JSON.stringify(contract, null, 2));
          event.currentTarget.textContent = "Copied";
          setTimeout(() => { event.currentTarget.textContent = "Copy JSON"; }, 1200);
        });
      }
      syncHash();
    }

    $("#search").addEventListener("input", event => renderList(event.target.value));
    document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
      activeTab = tab.dataset.tab;
      renderContract();
    }));
    window.addEventListener("hashchange", () => { loadHash(); renderList($("#search").value); renderContract(); });

    loadHash();
    $("#contract-count").textContent = contracts.length;
    renderList();
    renderContract();
  </script>
</body>
</html>
'''


if __name__ == "__main__":
    path = build()
    print(path)
