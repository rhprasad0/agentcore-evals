const root = document.getElementById("workbench");

const state = {
  dataset: null,
  selectedId: null,
  draftId: null,
  draftRow: null,
  filters: { search: "", family: "all", review: "all", author: "all" },
  revealExpected: false,
  editorTab: "expected",
  error: null,
  rawError: null,
};

function element(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === null) continue;
    if (name === "class") node.className = value;
    else if (name === "text") node.textContent = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2).toLowerCase(), value);
    else if (name === "checked") node.checked = Boolean(value);
    else if (name === "disabled") node.disabled = Boolean(value);
    else if (name === "value") node.value = value;
    else node.setAttribute(name, value);
  }
  for (const child of children.flat()) {
    if (child === undefined || child === null) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function normalized(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function selectedRow() {
  const row = state.dataset.rows.find((candidate) => candidate.exampleId === state.selectedId);
  if (!row) return null;
  if (state.draftId !== row.exampleId) {
    state.draftId = row.exampleId;
    state.draftRow = clone(row);
    state.rawError = null;
  }
  return row;
}

function isFinalized() {
  return state.dataset.manifest.reviewStatus === "human-reviewed";
}

function visibleRows() {
  const { search, family, review, author } = state.filters;
  const needle = normalized(search);
  return state.dataset.rows.filter((row) => {
    const haystack = normalized([
      row.exampleId,
      row.prompt,
      row.scenarioFamily,
      ...row.tags,
      ...row.expected.toolIds,
      ...row.expected.mustNotCall,
      ...row.expected.argConstraints.map((constraint) => `${constraint.toolId} ${constraint.path}`),
      row.failureInjection?.toolId,
    ].join(" "));
    return (
      (!needle || haystack.includes(needle)) &&
      (family === "all" || row.scenarioFamily === family) &&
      (review === "all" || row.provenance.reviewStatus === review) &&
      (author === "all" || row.provenance.authoringMethod === author)
    );
  });
}

function synchronizeSelection(rows) {
  const requestedId = decodeURIComponent(window.location.hash.slice(1));
  const usableId = rows.some((row) => row.exampleId === requestedId)
    ? requestedId
    : rows.some((row) => row.exampleId === state.selectedId)
      ? state.selectedId
      : rows[0]?.exampleId;
  const selectionChanged = state.selectedId !== usableId;
  state.selectedId = usableId || null;
  if (selectionChanged) {
    state.draftId = null;
    state.revealExpected = false;
    state.editorTab = "expected";
  }
  if (state.selectedId && window.location.hash !== `#${encodeURIComponent(state.selectedId)}`) {
    history.replaceState(null, "", `#${encodeURIComponent(state.selectedId)}`);
  }
}

function selectRow(exampleId) {
  state.selectedId = exampleId;
  state.draftId = null;
  state.revealExpected = false;
  state.editorTab = "expected";
  window.location.hash = encodeURIComponent(exampleId);
  render();
}

function makeOption(value, label = value) {
  return element("option", { value, text: label });
}

function selectControl(values, currentValue, onChange, label) {
  const control = element("select", { "aria-label": label, onChange });
  for (const value of values) control.append(makeOption(value));
  control.value = currentValue;
  return control;
}

function setError(error) {
  state.error = error;
  render();
}

function clearError() {
  state.error = null;
}

async function loadDataset() {
  try {
    const response = await fetch("/api/dataset", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.message || "Unable to load the dataset.");
    state.dataset = payload;
    const rows = visibleRows();
    synchronizeSelection(rows);
    clearError();
    render();
  } catch (error) {
    root.replaceChildren(element("p", { class: "loading", text: `Unable to load local data: ${error.message}` }));
  }
}

function renderHeader() {
  const { manifest, summary } = state.dataset;
  const reviewed = summary.reviewCounts.reviewed;
  const total = summary.rowCount;
  const percent = total ? (reviewed / total) * 100 : 0;
  const binding = `${manifest.agentManifest.manifestId}@${manifest.agentManifest.version}`;
  const header = element("header", { class: "app-header" });
  const top = element("div", { class: "header-top" });
  top.append(
    element("div", { class: "brand" },
      element("h1", { text: "Corpus review workbench" }),
      element("code", { text: `${manifest.datasetId}@${manifest.version}` }),
    ),
    element("span", {
      class: `status-pill ${isFinalized() ? "finalized" : "draft"}`,
      text: manifest.reviewStatus,
    }),
  );
  header.append(top);
  header.append(element("div", { class: "header-meta" },
    element("span", { text: `Exact agent binding: ${binding}` }),
    element("span", { text: `Reviewed ${reviewed} / ${total}` }),
    element("div", { class: "progress", title: `${reviewed} of ${total} rows reviewed` },
      element("span", { style: `width: ${percent}%` }),
    ),
  ));
  const families = Object.entries(summary.familyCounts).map(([family, count]) =>
    element("span", { class: "summary-item", text: `${family}: ${count}` }),
  );
  header.append(element("div", { class: "summary-strip" }, families));
  return header;
}

function renderRail(rows) {
  const rail = element("aside", { class: "rail", "aria-label": "Corpus rows" });
  const search = element("input", {
    type: "search",
    placeholder: "Search rows, tools, tags, prompt…",
    value: state.filters.search,
    "aria-label": "Search corpus rows",
    onInput: (event) => {
      state.filters.search = event.target.value;
      state.draftId = null;
      refreshFilteredView();
    },
  });
  rail.append(search);
  const metadata = state.dataset.editorMetadata;
  const filters = element("div", { class: "filter-row" });
  const familyControl = selectControl(["all", ...metadata.scenarioFamilies], state.filters.family, (event) => {
    state.filters.family = event.target.value;
    state.draftId = null;
    synchronizeSelection(visibleRows());
    render();
  }, "Scenario family");
  const reviewControl = selectControl(["all", "pending", "reviewed"], state.filters.review, (event) => {
    state.filters.review = event.target.value;
    state.draftId = null;
    synchronizeSelection(visibleRows());
    render();
  }, "Review status");
  const authorControl = selectControl(["all", "hand-authored", "generated"], state.filters.author, (event) => {
    state.filters.author = event.target.value;
    state.draftId = null;
    synchronizeSelection(visibleRows());
    render();
  }, "Authoring method");
  familyControl.options[0].textContent = "All families";
  reviewControl.options[0].textContent = "All review states";
  authorControl.options[0].textContent = "All authors";
  filters.append(familyControl, reviewControl, authorControl);
  rail.append(filters);
  rail.append(renderRowList(rows));
  return rail;
}

function renderRowList(rows) {
  const list = element("div", { class: "row-list" });
  if (!rows.length) {
    list.append(element("p", { class: "empty-rail", text: "No rows match these filters." }));
  }
  for (const row of rows) {
    const card = element("button", {
      class: `row-card ${row.exampleId === state.selectedId ? "selected" : ""}`,
      type: "button",
      onClick: () => selectRow(row.exampleId),
    });
    const meta = element("span", { class: "row-meta" },
      element("span", {}, element("span", { class: `review-dot ${row.provenance.reviewStatus}` }), ` ${row.exampleId}`),
      element("span", { class: "family-badge", text: row.scenarioFamily }),
    );
    card.append(meta, element("span", { class: "prompt-excerpt", text: row.prompt }));
    list.append(card);
  }
  return list;
}

function refreshFilteredView() {
  const rows = visibleRows();
  synchronizeSelection(rows);
  root.querySelector(".row-list")?.replaceWith(renderRowList(rows));
  root.querySelector(".inspector")?.replaceWith(renderInspector());
}

function renderError() {
  if (!state.error) return null;
  const message = element("div", { class: "error-region" });
  message.append(element("strong", { text: state.error.message || "The server rejected this change." }));
  if (state.error.details?.length) {
    const list = element("ul");
    for (const detail of state.error.details) list.append(element("li", { text: `${detail.path}: ${detail.message}` }));
    message.append(list);
  }
  if (state.error.code === "stale_revision") {
    message.append(element("button", { type: "button", text: "Reload current version", onClick: loadDataset }));
  }
  return message;
}

function updateDraft(mutator, { renderAfter = true } = {}) {
  mutator(state.draftRow);
  state.rawError = null;
  clearError();
  if (renderAfter) render();
}

function checkboxToolList(title, toolIds, activeIds, onToggle) {
  const block = element("section", { class: "editor-block" });
  block.append(element("h4", { text: title }));
  const list = element("div", { class: "toggle-list" });
  for (const toolId of toolIds) {
    const box = element("input", {
      type: "checkbox",
      checked: activeIds.includes(toolId),
      disabled: isFinalized(),
      onChange: (event) => onToggle(toolId, event.target.checked),
    });
    list.append(element("label", {}, box, element("code", { text: toolId })));
  }
  block.append(list);
  return block;
}

function parseList(text) {
  return text.split("\n").map((value) => value.trim()).filter(Boolean);
}

function predicateValue(constraint) {
  const predicate = state.dataset.editorMetadata.constraintPredicates.find((key) => key in constraint) || "equals";
  return predicate === "absent" ? "true" : JSON.stringify(constraint[predicate] ?? "");
}

function coercePredicateValue(predicate, rawValue) {
  if (predicate === "absent") return true;
  try {
    return JSON.parse(rawValue);
  } catch {
    return rawValue;
  }
}

function renderConstraintEditor() {
  const block = element("section", { class: "editor-block" });
  const heading = element("div", { class: "section-heading" }, element("h4", { text: "Argument constraints" }));
  heading.append(element("button", {
    type: "button", text: "Add constraint", disabled: isFinalized(), onClick: () => updateDraft((row) => {
      const toolId = row.expected.toolIds[0] || Object.keys(state.dataset.editorMetadata.contractInputs)[0];
      const field = state.dataset.editorMetadata.contractInputs[toolId][0];
      row.expected.argConstraints.push({ toolId, path: `$.${field}`, equals: "" });
    }),
  }));
  block.append(heading);
  const table = element("table", { class: "constraint-table" });
  table.append(element("thead", {}, element("tr", {},
    element("th", { text: "Tool" }), element("th", { text: "Input field" }),
    element("th", { text: "Predicate" }), element("th", { text: "Value (JSON or text)" }), element("th", { text: "" }),
  )));
  const body = element("tbody");
  state.draftRow.expected.argConstraints.forEach((constraint, index) => {
    const row = element("tr");
    const toolControl = selectControl(Object.keys(state.dataset.editorMetadata.contractInputs), constraint.toolId, (event) => updateDraft((draft) => {
      const nextToolId = event.target.value;
      draft.expected.argConstraints[index].toolId = nextToolId;
      draft.expected.argConstraints[index].path = `$.${state.dataset.editorMetadata.contractInputs[nextToolId][0]}`;
    }), "Constraint tool");
    toolControl.disabled = isFinalized();
    const fields = state.dataset.editorMetadata.contractInputs[constraint.toolId] || [];
    const fieldControl = selectControl(fields, constraint.path.slice(2), (event) => updateDraft((draft) => {
      draft.expected.argConstraints[index].path = `$.${event.target.value}`;
    }), "Constraint input field");
    fieldControl.disabled = isFinalized();
    const activePredicate = state.dataset.editorMetadata.constraintPredicates.find((key) => key in constraint) || "equals";
    const predicateControl = selectControl(state.dataset.editorMetadata.constraintPredicates, activePredicate, (event) => updateDraft((draft) => {
      const target = draft.expected.argConstraints[index];
      for (const key of state.dataset.editorMetadata.constraintPredicates) delete target[key];
      target[event.target.value] = event.target.value === "absent" ? true : "";
    }), "Constraint predicate");
    predicateControl.disabled = isFinalized();
    const valueControl = element("input", {
      value: predicateValue(constraint), disabled: isFinalized() || activePredicate === "absent", "aria-label": "Constraint value",
      onInput: (event) => updateDraft((draft) => {
        draft.expected.argConstraints[index][activePredicate] = coercePredicateValue(activePredicate, event.target.value);
      }, { renderAfter: false }),
    });
    const remove = element("button", { type: "button", text: "Remove", disabled: isFinalized(), onClick: () => updateDraft((draft) => {
      draft.expected.argConstraints.splice(index, 1);
    }) });
    row.append(
      element("td", {}, toolControl), element("td", {}, fieldControl), element("td", {}, predicateControl), element("td", {}, valueControl), element("td", {}, remove),
    );
    body.append(row);
  });
  table.append(body);
  block.append(table);
  return block;
}

function renderExpectedEditor() {
  const row = state.draftRow;
  const metadata = state.dataset.editorMetadata;
  const form = element("div", { class: "editor-form" });
  const toolIds = Object.keys(metadata.contractInputs);
  const grid = element("div", { class: "editor-grid" });
  grid.append(
    checkboxToolList("Expected tools", toolIds, row.expected.toolIds, (toolId, checked) => updateDraft((draft) => {
      draft.expected.toolIds = checked
        ? [...draft.expected.toolIds, toolId]
        : draft.expected.toolIds.filter((candidate) => candidate !== toolId);
    })),
    checkboxToolList("Forbidden tools", toolIds, row.expected.mustNotCall, (toolId, checked) => updateDraft((draft) => {
      draft.expected.mustNotCall = checked
        ? [...draft.expected.mustNotCall, toolId]
        : draft.expected.mustNotCall.filter((candidate) => candidate !== toolId);
    })),
  );
  const countBlock = element("section", { class: "editor-block" }, element("h4", { text: "Call bounds" }));
  for (const field of ["minCalls", "maxCalls"]) {
    const input = element("input", {
      type: "number", min: "0", value: row.expected[field], disabled: isFinalized(), "aria-label": field,
      onInput: (event) => updateDraft((draft) => { draft.expected[field] = Number(event.target.value); }, { renderAfter: false }),
    });
    countBlock.append(element("label", { class: "inline-label" }, field, input));
  }
  const responseBlock = element("section", { class: "editor-block" }, element("h4", { text: "Response requirements" }));
  for (const [field, label] of [["responseMust", "Must include"], ["responseMustNot", "Must not include"]]) {
    const input = element("textarea", {
      value: row.expected[field].join("\n"), disabled: isFinalized(), "aria-label": label,
      onInput: (event) => updateDraft((draft) => { draft.expected[field] = parseList(event.target.value); }, { renderAfter: false }),
    });
    responseBlock.append(element("label", { class: "inline-label" }, label), input);
  }
  grid.append(countBlock, responseBlock);
  form.append(grid, renderConstraintEditor(), renderFailureEditor());
  return form;
}

function renderFailureEditor() {
  const block = element("section", { class: "editor-block" }, element("h4", { text: "Failure injection" }));
  const none = state.draftRow.failureInjection === null;
  const enabled = element("input", {
    type: "checkbox", checked: !none, disabled: isFinalized(), onChange: (event) => updateDraft((draft) => {
      draft.failureInjection = event.target.checked
        ? { toolId: draft.expected.toolIds[0] || Object.keys(state.dataset.editorMetadata.contractInputs)[0], kind: "timeout", retryable: true }
        : null;
    }),
  });
  block.append(element("label", { class: "inline-label" }, enabled, "Include scripted failure"));
  if (none) return block;
  const failure = state.draftRow.failureInjection;
  const fields = element("div", { class: "field-row" });
  const controls = [
    ["Tool", Object.keys(state.dataset.editorMetadata.contractInputs), "toolId"],
    ["Kind", state.dataset.editorMetadata.failureKinds, "kind"],
    ["Source", ["", ...state.dataset.editorMetadata.failureSources], "source"],
  ];
  for (const [label, values, key] of controls) {
    const control = selectControl(values, failure[key] || "", (event) => updateDraft((draft) => {
      if (event.target.value) draft.failureInjection[key] = event.target.value;
      else delete draft.failureInjection[key];
    }), label);
    control.disabled = isFinalized();
    fields.append(element("label", {}, label, control));
  }
  const retry = element("input", {
    type: "checkbox", checked: failure.retryable, disabled: isFinalized(), onChange: (event) => updateDraft((draft) => {
      draft.failureInjection.retryable = event.target.checked;
    }),
  });
  fields.append(element("label", { class: "inline-label" }, retry, "Retryable"));
  block.append(fields);
  return block;
}

function renderRawEditor() {
  const panel = element("div", {});
  const refreshRawError = () => {
    panel.querySelector(".error-region")?.remove();
    if (state.rawError) {
      panel.prepend(element("div", { class: "error-region", text: `Local JSON parse error: ${state.rawError}` }));
    }
    const saveButton = root.querySelector('[data-action="save-row"]');
    if (saveButton) saveButton.disabled = isFinalized() || Boolean(state.rawError);
  };
  const textarea = element("textarea", {
    class: "raw-editor",
    value: JSON.stringify(state.draftRow, null, 2),
    disabled: isFinalized(),
    "aria-label": "Complete raw row JSON",
    onInput: (event) => {
      try {
        const parsed = JSON.parse(event.target.value);
        state.draftRow = parsed;
        state.rawError = null;
      } catch (error) {
        state.rawError = error.message;
      }
      refreshRawError();
    },
  });
  refreshRawError();
  panel.append(textarea);
  return panel;
}

function renderInspector() {
  const currentRow = selectedRow();
  const inspector = element("section", { class: "inspector", "aria-label": "Selected row inspector" });
  if (!currentRow) {
    inspector.append(element("div", { class: "panel" }, element("h2", { text: "No matching row" }), element("p", { text: "Adjust the filters to select a row." })));
    return inspector;
  }
  if (isFinalized()) {
    inspector.append(element("div", { class: "notice finalized", text: "This dataset is human-reviewed and frozen. Subsequent changes require a versioned errata workflow." }));
  }
  const promptPanel = element("section", { class: "panel" });
  promptPanel.append(
    element("div", { class: "section-heading" },
      element("h2", { text: currentRow.exampleId }),
      element("span", { class: "family-badge", text: currentRow.scenarioFamily }),
      element("span", { class: `status-pill ${currentRow.provenance.reviewStatus === "reviewed" ? "finalized" : "draft"}`, text: currentRow.provenance.reviewStatus }),
    ),
    element("p", { class: "prompt", text: currentRow.prompt }),
  );
  const reveal = element("button", {
    type: "button", class: "primary", text: state.revealExpected ? "Hide expected behavior" : "Reveal expected behavior",
    onClick: () => { state.revealExpected = !state.revealExpected; render(); },
  });
  promptPanel.append(reveal);
  inspector.append(promptPanel);
  if (!state.revealExpected) return inspector;

  const editorPanel = element("section", { class: "panel" });
  const tabs = element("div", { class: "tabs" });
  for (const [key, label] of [["expected", "Expected behavior"], ["raw", "Advanced raw JSON"]]) {
    tabs.append(element("button", {
      type: "button", class: `tab ${state.editorTab === key ? "active" : ""}`, text: label,
      onClick: () => { state.editorTab = key; state.rawError = null; render(); },
    }));
  }
  editorPanel.append(tabs, state.editorTab === "expected" ? renderExpectedEditor() : renderRawEditor());
  const serverError = renderError();
  if (serverError) editorPanel.append(serverError);
  const actions = element("div", { class: "action-row" });
  actions.append(
    element("button", { type: "button", class: "primary", text: "Save row", "data-action": "save-row", disabled: isFinalized() || Boolean(state.rawError), onClick: () => saveRow(state.draftRow) }),
    element("button", { type: "button", text: "Mark reviewed", disabled: isFinalized(), onClick: () => markReviewStatus("reviewed") }),
    element("button", { type: "button", text: "Return to pending", disabled: isFinalized(), onClick: () => markReviewStatus("pending") }),
    element("button", { type: "button", class: "danger", text: "Finalize dataset review", disabled: isFinalized(), onClick: finalizeDataset }),
  );
  editorPanel.append(actions);
  inspector.append(editorPanel);
  return inspector;
}

async function saveRow(row) {
  if (state.rawError) return;
  clearError();
  try {
    const response = await fetch(`/api/rows/${encodeURIComponent(row.exampleId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ row, revision: state.dataset.revision }),
    });
    const payload = await response.json();
    if (!response.ok) {
      state.error = payload.error || { message: "The server rejected this row." };
      render();
      return;
    }
    await loadDataset();
  } catch (error) {
    state.error = { message: `Save failed: ${error.message}`, details: [] };
    render();
  }
}

async function markReviewStatus(reviewStatus) {
  const candidate = clone(state.draftRow);
  candidate.provenance.reviewStatus = reviewStatus;
  await saveRow(candidate);
}

async function finalizeDataset() {
  clearError();
  try {
    const response = await fetch("/api/finalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision: state.dataset.revision }),
    });
    const payload = await response.json();
    if (!response.ok) {
      state.error = payload.error || { message: "The server rejected finalization." };
      render();
      return;
    }
    state.dataset = payload;
    state.draftId = null;
    clearError();
    render();
  } catch (error) {
    state.error = { message: `Finalization failed: ${error.message}`, details: [] };
    render();
  }
}

function render() {
  if (!state.dataset) return;
  const rows = visibleRows();
  synchronizeSelection(rows);
  root.replaceChildren(renderHeader(), element("div", { class: "workspace" }, renderRail(rows), renderInspector()));
}

window.addEventListener("hashchange", () => {
  if (!state.dataset) return;
  const rows = visibleRows();
  synchronizeSelection(rows);
  state.draftId = null;
  render();
});

loadDataset();
