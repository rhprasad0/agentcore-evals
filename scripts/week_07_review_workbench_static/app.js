const app = document.getElementById("review-app");

const state = {
  payload: null,
  index: 0,
  rubricVisible: false,
  saving: false,
  filter: "all",
};

const verdictCopy = {
  "pass": ["Pass", "Expectation and observed behavior align."],
  "agent-bug": ["Agent bug", "The expectation is sound; the agent behavior is wrong."],
  "dataset-bug": ["Dataset bug", "The expected behavior is not defensible."],
  "contract-ambiguity": ["Contract ambiguity", "The capability boundary permits reasonable disagreement."],
  "instrument-error": ["Instrument error", "No trustworthy canonical trace exists."],
};

const checkCopy = {
  expectationDefensible: "The expected behavior is defensible",
  toolChoiceAndCount: "Tool choice and call count are correct",
  arguments: "Tool arguments satisfy the expectation",
  resultHandling: "Tool results or failures were handled correctly",
  responseRequirements: "The final response meets the stated requirements",
  noForbiddenBehavior: "No forbidden behavior or fabrication appears",
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(label, className, handler) {
  const node = element("button", className, label);
  node.type = "button";
  node.addEventListener("click", handler);
  return node;
}

function formatVerdict(verdict) {
  return verdictCopy[verdict]?.[0] || "Unreviewed";
}

function currentRow() {
  return state.payload.rows[state.index];
}

function visibleRows() {
  return state.payload.rows.filter((row) => {
    if (state.filter === "remaining") return !row.review;
    if (state.filter === "reviewed") return Boolean(row.review);
    return true;
  });
}

function setRow(exampleId) {
  const index = state.payload.rows.findIndex((row) => row.exampleId === exampleId);
  if (index < 0) return;
  state.index = index;
  state.rubricVisible = false;
  window.location.hash = exampleId;
  renderWorkspace();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function moveRow(offset) {
  const next = Math.min(Math.max(state.index + offset, 0), state.payload.rows.length - 1);
  setRow(state.payload.rows[next].exampleId);
}

function toggleRubric() {
  state.rubricVisible = !state.rubricVisible;
  renderWorkspace();
}

function renderWorkspace() {
  const shell = element("div", "app-shell");
  shell.append(renderHeader(), renderSidebar(), renderCase());
  app.replaceChildren(shell);
}

function renderHeader() {
  const header = element("header", "topbar");
  const brand = element("div", "brand");
  const mark = element("div", "brand-mark", "W7");
  const titles = element("div", "brand-titles");
  titles.append(
    element("strong", "brand-name", "Frozen trace review"),
    element("span", "brand-subtitle", "Private · loopback-only · saved locally")
  );
  brand.append(mark, titles);

  const progress = element("div", "header-progress");
  const summary = state.payload.summary;
  const progressText = element(
    "span",
    "progress-label",
    `${summary.reviewed} of ${summary.total} reviewed`
  );
  const track = element("div", "progress-track");
  const fill = element("div", "progress-fill");
  fill.style.width = `${(summary.reviewed / summary.total) * 100}%`;
  track.append(fill);
  progress.append(progressText, track);

  const actions = element("div", "header-actions");
  actions.append(button("Export JSON", "button secondary", downloadReview));
  header.append(brand, progress, actions);
  return header;
}

function renderSidebar() {
  const sidebar = element("aside", "sidebar");
  const filterGroup = element("div", "filter-group");
  for (const [value, label] of [["all", "All"], ["remaining", "Remaining"], ["reviewed", "Reviewed"]]) {
    const control = button(label, `filter-button${state.filter === value ? " active" : ""}`, () => {
      state.filter = value;
      renderWorkspace();
    });
    filterGroup.append(control);
  }
  const list = element("nav", "case-list");
  list.setAttribute("aria-label", "Frozen review rows");
  for (const row of visibleRows()) {
    const index = state.payload.rows.indexOf(row);
    const item = button("", `case-item${index === state.index ? " selected" : ""}`, () => setRow(row.exampleId));
    item.removeAttribute("aria-label");
    const ordinal = element("span", "case-ordinal", String(index + 1).padStart(2, "0"));
    const body = element("span", "case-item-body");
    body.append(
      element("strong", "case-id", row.exampleId),
      element("span", "case-family", row.scenarioFamily)
    );
    const status = element(
      "span",
      `case-status ${row.review ? `verdict-${row.review.verdict}` : "pending"}`,
      row.review ? "●" : "○"
    );
    status.title = row.review ? formatVerdict(row.review.verdict) : "Unreviewed";
    item.append(ordinal, body, status);
    list.append(item);
  }
  const hint = element("div", "shortcut-hint");
  hint.append(
    element("span", "key", "←"),
    element("span", "key", "→"),
    document.createTextNode(" navigate · "),
    element("span", "key", "R"),
    document.createTextNode(" reveal")
  );
  sidebar.append(filterGroup, list, hint);
  return sidebar;
}

function renderCase() {
  const row = currentRow();
  const main = element("main", "case-main");
  const heading = element("section", "case-heading");
  const meta = element("div", "eyebrow");
  meta.append(
    element("span", "ordinal-label", `CASE ${String(state.index + 1).padStart(2, "0")} / ${state.payload.rows.length}`),
    element("span", "family-badge", row.scenarioFamily)
  );
  const title = element("h1", "case-title", row.exampleId);
  const tags = element("div", "tag-list");
  row.tags.forEach((tag) => tags.append(element("span", "tag", tag)));
  heading.append(meta, title, tags);

  main.append(
    heading,
    renderPrompt(row),
    renderObserved(row),
    renderRubric(row),
    renderReviewForm(row),
    renderFooterNav()
  );
  return main;
}

function renderPrompt(row) {
  const section = card("Prompt", "What the agent received", "prompt-card");
  const quote = element("blockquote", "prompt-text", row.prompt);
  section.append(quote);
  return section;
}

function renderObserved(row) {
  const section = card("Observed trace", "What actually happened", "observed-card");
  const stats = element("div", "stats-row");
  const usage = row.observed.tokenUsage || {};
  for (const [label, value] of [
    ["Tool calls", row.observed.toolCalls.length],
    ["Spans", row.observed.spanCount],
    ["Tokens", usage.total ?? "—"],
  ]) {
    const stat = element("div", "stat");
    stat.append(element("strong", "stat-value", String(value)), element("span", "stat-label", label));
    stats.append(stat);
  }
  section.append(stats);

  const callsHeading = element("h3", "subheading", "Ordered tool calls");
  section.append(callsHeading);
  if (row.observed.toolCalls.length === 0) {
    section.append(element("div", "empty-state", "No tool calls were observed."));
  } else {
    const timeline = element("div", "tool-timeline");
    row.observed.toolCalls.forEach((call, index) => timeline.append(renderToolCall(call, index)));
    section.append(timeline);
  }

  const responseHeading = element("h3", "subheading response-heading", "Final response");
  const response = element("pre", "response-text");
  response.textContent = row.observed.response;
  section.append(responseHeading, response);
  return section;
}

function renderToolCall(call, index) {
  const item = element("details", "tool-call");
  if (index === 0) item.open = true;
  const summary = element("summary", "tool-summary");
  const toolName = call.tool ? `${call.tool.toolId}@${call.tool.contractVersion}` : call.observedToolName;
  const ok = call.result?.ok === true;
  const resultKind = ok ? "success" : (call.result?.failureKind || "unknown");
  summary.append(
    element("span", "timeline-index", String(index + 1)),
    element("strong", "tool-name", toolName),
    element("span", `result-badge ${ok ? "success" : "failure"}`, resultKind)
  );
  const body = element("div", "tool-body");
  body.append(
    jsonBlock("Arguments", call.arguments),
    jsonBlock("Normalized result", call.result)
  );
  const reasoning = element("div", "reasoning-block");
  reasoning.append(
    element("span", "mini-label", "Block-local selection reasoning"),
    element("p", call.selectionReasoning ? "reasoning-text" : "reasoning-null", call.selectionReasoning || "null · no attributable local text")
  );
  body.append(reasoning);
  item.append(summary, body);
  return item;
}

function jsonBlock(label, value) {
  const wrapper = element("div", "json-block");
  wrapper.append(element("span", "mini-label", label));
  const pre = element("pre", "json-view");
  pre.textContent = JSON.stringify(value, null, 2);
  wrapper.append(pre);
  return wrapper;
}

function renderRubric(row) {
  const section = card("Expected behavior", "Frozen before model output", "rubric-card");
  if (!state.rubricVisible) {
    const veil = element("div", "rubric-veil");
    const icon = element("div", "veil-icon", "◌");
    const copy = element("div", "veil-copy");
    copy.append(
      element("strong", "veil-title", "Expectation hidden to reduce anchoring"),
      element("p", "veil-text", "Inspect the prompt and trace first. Reveal the frozen rubric when you are ready to compare.")
    );
    veil.append(icon, copy, button("Reveal frozen rubric", "button primary", toggleRubric));
    section.append(veil);
    return section;
  }

  const expected = row.expected;
  const grid = element("div", "rubric-grid");
  grid.append(
    rubricItem("Expected calls", `${expected.minCalls}–${expected.maxCalls}`),
    rubricItem("Allowed tool sequence", expected.toolIds.length ? expected.toolIds.join(" → ") : "No tools"),
    rubricItem("Forbidden tools", expected.mustNotCall.length ? expected.mustNotCall.join(", ") : "None")
  );
  section.append(grid);
  section.append(listBlock("Response must", expected.responseMust, "positive"));
  section.append(listBlock("Response must not", expected.responseMustNot, "negative"));
  if (expected.argConstraints.length) section.append(jsonBlock("Argument constraints", expected.argConstraints));
  if (row.failureInjection) section.append(jsonBlock("Failure injection", row.failureInjection));
  section.append(button("Hide rubric", "button ghost", toggleRubric));
  return section;
}

function rubricItem(label, value) {
  const item = element("div", "rubric-item");
  item.append(element("span", "mini-label", label), element("strong", "rubric-value", value));
  return item;
}

function listBlock(label, values, tone) {
  const block = element("div", `requirement-block ${tone}`);
  block.append(element("span", "mini-label", label));
  if (!values.length) {
    block.append(element("p", "requirement-empty", "None declared"));
    return block;
  }
  const list = element("ul", "requirement-list");
  values.forEach((value) => list.append(element("li", "", value)));
  block.append(list);
  return block;
}

function renderReviewForm(row) {
  const section = card("Your review", "Saved privately to ignored run storage", "review-card");
  const form = element("form", "review-form");
  form.id = "review-form";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await saveAndNext();
  });
  const saved = row.review;

  form.append(element("h3", "form-heading", "Verdict"));
  const verdicts = element("div", "verdict-grid");
  for (const verdict of state.payload.reviewMetadata.verdicts) {
    const label = element("label", `verdict-option verdict-option-${verdict}`);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "verdict";
    input.value = verdict;
    input.checked = saved?.verdict === verdict;
    const copy = element("span", "verdict-copy");
    copy.append(
      element("strong", "verdict-title", verdictCopy[verdict][0]),
      element("span", "verdict-description", verdictCopy[verdict][1])
    );
    label.append(input, copy);
    verdicts.append(label);
  }
  form.append(verdicts);

  const formGrid = element("div", "form-grid");
  const checksPanel = element("fieldset", "checks-panel");
  checksPanel.append(element("legend", "form-heading", "Review checks"));
  for (const field of state.payload.reviewMetadata.checkFields) {
    const label = element("label", "check-row");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = field;
    input.checked = saved?.checks?.[field] === true;
    label.append(input, element("span", "", checkCopy[field]));
    checksPanel.append(label);
  }

  const notesPanel = element("div", "notes-panel");
  const confidenceLabel = element("label", "field-label", "Confidence");
  const confidence = document.createElement("select");
  confidence.name = "confidence";
  confidence.className = "select-control";
  confidence.append(element("option", "", "Select confidence…"));
  confidence.firstChild.value = "";
  for (const level of state.payload.reviewMetadata.confidenceLevels) {
    const option = element("option", "", level[0].toUpperCase() + level.slice(1));
    option.value = level;
    option.selected = saved?.confidence === level;
    confidence.append(option);
  }
  confidenceLabel.append(confidence);

  const notesLabel = element("label", "field-label", "Notes");
  const notes = document.createElement("textarea");
  notes.name = "notes";
  notes.className = "notes-control";
  notes.rows = 7;
  notes.maxLength = 5000;
  notes.placeholder = "Record the evidence for your verdict. What happened, and why does it matter?";
  notes.value = saved?.notes || "";
  notesLabel.append(notes);
  notesPanel.append(confidenceLabel, notesLabel);
  formGrid.append(checksPanel, notesPanel);
  form.append(formGrid);

  const status = element("div", "save-status");
  status.id = "save-status";
  const formActions = element("div", "form-actions");
  formActions.append(
    status,
    button("Save", "button secondary", () => saveReview(false)),
    button(state.index === state.payload.rows.length - 1 ? "Save review" : "Save & next", "button primary", saveAndNext)
  );
  form.append(formActions);
  section.append(form);
  return section;
}

function card(kicker, title, className) {
  const section = element("section", `card ${className}`);
  const head = element("div", "card-head");
  head.append(element("span", "card-kicker", kicker), element("h2", "card-title", title));
  section.append(head);
  return section;
}

function renderFooterNav() {
  const nav = element("nav", "footer-nav");
  nav.append(
    button("← Previous case", "button ghost", () => moveRow(-1)),
    element("span", "footer-position", `${state.index + 1} / ${state.payload.rows.length}`),
    button("Next case →", "button ghost", () => moveRow(1))
  );
  return nav;
}

function collectReview() {
  const form = document.getElementById("review-form");
  const data = new FormData(form);
  const verdict = data.get("verdict");
  const confidence = data.get("confidence");
  if (!verdict) throw new Error("Choose a verdict before saving.");
  if (!confidence) throw new Error("Choose a confidence level before saving.");
  const checks = {};
  state.payload.reviewMetadata.checkFields.forEach((field) => {
    checks[field] = data.get(field) === "on";
  });
  return {
    exampleId: currentRow().exampleId,
    verdict,
    confidence,
    checks,
    notes: data.get("notes") || "",
  };
}

async function saveReview(advance) {
  if (state.saving) return;
  const status = document.getElementById("save-status");
  try {
    const review = collectReview();
    state.saving = true;
    status.textContent = "Saving…";
    status.className = "save-status active";
    const response = await fetch(`/api/reviews/${review.exampleId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision: state.payload.revision, review }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Review could not be saved.");
    state.payload = body;
    state.saving = false;
    if (advance && state.index < state.payload.rows.length - 1) {
      setRow(state.payload.rows[state.index + 1].exampleId);
    } else {
      renderWorkspace();
      const updatedStatus = document.getElementById("save-status");
      updatedStatus.textContent = "Saved locally";
      updatedStatus.className = "save-status success";
    }
  } catch (error) {
    state.saving = false;
    status.textContent = error.message;
    status.className = "save-status error";
  }
}

async function saveAndNext() {
  await saveReview(true);
}

async function downloadReview() {
  const response = await fetch("/api/export", { cache: "no-store" });
  if (!response.ok) return;
  const documentValue = await response.json();
  const blob = new Blob([JSON.stringify(documentValue, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "week-07-human-review.json";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function loadWorkspace() {
  const response = await fetch("/api/review", { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load the frozen review sample.");
  state.payload = await response.json();
  const requested = window.location.hash.slice(1);
  const requestedIndex = state.payload.rows.findIndex((row) => row.exampleId === requested);
  state.index = requestedIndex >= 0 ? requestedIndex : 0;
  window.location.hash = state.payload.rows[state.index].exampleId;
  renderWorkspace();
}

window.addEventListener("hashchange", () => {
  if (!state.payload) return;
  const requested = window.location.hash.slice(1);
  const index = state.payload.rows.findIndex((row) => row.exampleId === requested);
  if (index >= 0 && index !== state.index) {
    state.index = index;
    state.rubricVisible = false;
    renderWorkspace();
  }
});

window.addEventListener("keydown", (event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") saveAndNext();
    return;
  }
  if (event.key === "ArrowLeft") moveRow(-1);
  if (event.key === "ArrowRight") moveRow(1);
  if (event.key.toLowerCase() === "r") toggleRubric();
});

loadWorkspace().catch((error) => {
  const panel = element("div", "fatal-error");
  panel.append(element("strong", "", "Review workbench could not start"), element("p", "", error.message));
  app.replaceChildren(panel);
});

window.saveAndNext = saveAndNext;
window.renderWorkspace = renderWorkspace;
window.toggleRubric = toggleRubric;
window.downloadReview = downloadReview;
