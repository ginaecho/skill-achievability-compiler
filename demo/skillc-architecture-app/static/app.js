const samples = {
  skill: `---
name: publish-brief
allowed-tools: [research_topic, write_report]
---
# Publish a research brief

Tools: research_topic, write_report.

1. Use \`research_topic\` to gather verified evidence.
2. Use \`write_report\` to publish the final brief.

Your job is finished when the evidence is **researched** and the brief is **published**.`,
  agent: `---
name: release-agent
tools: [inspect_build, deploy_release]
---
# Release agent

Tools: inspect_build, deploy_release.

First use \`inspect_build\` to confirm the artifact.
Then use \`deploy_release\` to publish it.

The task is finished when the build is **inspected** and the release is **deployed**.`,
  prompt: `Create a verified project summary.

Tools available: inspect_repository, write_summary.

First use \`inspect_repository\` to collect the project facts.
Then use \`write_summary\` to save the result.

You are finished when the repository is **inspected** and the summary is **written**.`
};

const form = document.querySelector("#intent-form");
const input = document.querySelector("#intent");
const environmentSource = document.querySelector("#environment-source");
const refreshEnvironment = document.querySelector("#refresh-environment");
const environmentMeta = document.querySelector("#environment-meta");
const discoveredGrants = document.querySelector("#discovered-grants");
const testedIntent = document.querySelector("#tested-intent");
const catalogCount = document.querySelector("#catalog-count");
const catalogMeta = document.querySelector("#catalog-meta");
const combineChecks = [...document.querySelectorAll(".combine-selector input")];
const combineNote = document.querySelector("#combine-note");
const compactionChoices = [...document.querySelectorAll("[name=compaction]")];
const azureSettings = document.querySelector("#azure-settings");
const projectEndpoint = document.querySelector("#foundry-project-endpoint");
const apiEndpoint = document.querySelector("#azure-openai-endpoint");
const azureModel = document.querySelector("#azure-model");
const azureAuth = document.querySelector("#azure-auth");
const runButton = document.querySelector("#run");
const terminal = document.querySelector("#terminal");
const runState = document.querySelector("#run-state");
const elapsed = document.querySelector("#elapsed");
const fileLabel = document.querySelector("#file-label");
const evidenceGraph = document.querySelector("#evidence-graph");
const graphState = document.querySelector("#graph-state");
const graphInputTitle = document.querySelector("#graph-input-title");
const graphInput = document.querySelector("#graph-input");
const graphOutputTitle = document.querySelector("#graph-output-title");
const graphOutput = document.querySelector("#graph-output");
const graphCode = document.querySelector("#graph-code");
const graphEffect = document.querySelector("#graph-effect");
const verdictSummary = document.querySelector("#verdict-summary");
const verdictLabel = document.querySelector("#verdict-label");
const verdictReason = document.querySelector("#verdict-reason");
const verdictDetail = document.querySelector("#verdict-detail");
const verdictExplanation = document.querySelector("#verdict-explanation");
const verdictExplanationText = document.querySelector("#verdict-explanation-text");
const tokenUsage = document.querySelector("#token-usage");
const tokenUsageRows = document.querySelector("#token-usage-rows");
let inputType = "skill";
let functionsSeen = 0;
let source = null;
let topics = new Map();
const INPUT_ORDER = ["skill", "agent", "prompt"];
let currentEnvironment = null;
let selectedStage = "receive";
let stageArtifacts = new Map();
let stageModules = new Map();
let activeTraceStage = "receive";
const inputBuffers = {...samples};

const graphStages = {
  receive: {
    title: "Receive intent", kind: "INPUT", x: 40, y: 30,
    input: "Browser-selected SKILL.md, agent.md, prompt, or composite",
    output: "Normalized temporary Markdown source",
    effect: "Defines the exact source text whose meaning the frontend must preserve."
  },
  compile: {
    title: "Extract requirements", kind: "FRONTEND", x: 400, y: 30,
    input: "Received Markdown source",
    output: "Requirement pack + compaction provenance",
    effect: "Determines what goal, required capabilities, roles, and protocol the trusted core will judge."
  },
  environment: {
    title: "Observed environment", kind: "ENV INPUT", x: 760, y: 30,
    input: "Cached skillc.env snapshot",
    output: "Observed tools, programs, permissions, and grants",
    effect: "Supplies independent evidence of what this runtime can actually provide."
  },
  bind: {
    title: "Bind requirements", kind: "BINDING", x: 400, y: 210,
    input: "Requirement pack + observed grants",
    output: "Environment-bound pack + unavailable frontier",
    effect: "Removes capability definitions not granted by the environment; missing required actions become refutable."
  },
  schema: {
    title: "Static validation", kind: "TRUSTED", x: 40, y: 390,
    input: "Environment-bound pack",
    output: "Validated normalized pack + digest",
    effect: "Malformed packs stop here and cannot reach the trusted decision procedure."
  },
  capability: {
    title: "Capability existence", kind: "TRUSTED", x: 400, y: 390,
    input: "Validated protocol + capability definitions",
    output: "Missing-capability frontier or pass",
    effect: "A missing required action directly yields IMPOSSIBLE [MISSING_CAPABILITY]."
  },
  interaction: {
    title: "Interaction checking", kind: "TRUSTED", x: 760, y: 390,
    input: "Roles, global protocol, and declared role behavior",
    output: "Role projections + conformance result",
    effect: "Unobservable choices or incompatible role behavior yield NON_PROJECTABLE or NON_CONFORMANT."
  },
  reachability: {
    title: "Goal reachability", kind: "SOLVER", x: 760, y: 560,
    input: "Validated, capable, realizable protocol",
    output: "Witness path or blocking frontier",
    effect: "Determines whether some abstract run reaches the declared goal."
  },
  verdict: {
    title: "Final verdict", kind: "DECISION", x: 400, y: 560,
    input: "First decisive check result",
    output: "ACHIEVABLE, IMPOSSIBLE, or UNKNOWN",
    effect: "Reports structural admission, sound refutation, or abstention; only ACHIEVABLE permits execution."
  }
};

// [from, to, label, side leaving `from`, side entering `to`]
const graphEdges = [
  ["receive", "compile", "source text", "right", "left"],
  ["compile", "bind", "requirement pack", "bottom", "top"],
  ["environment", "bind", "observed grants", "bottom", "right"],
  ["bind", "schema", "bound pack", "left", "top"],
  ["schema", "capability", "validated pack", "right", "left"],
  ["capability", "interaction", "if passed", "right", "left"],
  ["interaction", "reachability", "if passed", "bottom", "top"],
  ["reachability", "verdict", "decision evidence", "left", "right"]
];
const NODE_W = 200;
const NODE_H = 86;
const SIDE_NORMALS = {right: [1, 0], left: [-1, 0], top: [0, -1], bottom: [0, 1]};

input.value = inputBuffers.skill;
loadCatalog();
loadConfiguration();
loadEnvironment();
renderEvidenceGraph();

document.querySelectorAll("[data-type]").forEach(button => {
  button.addEventListener("click", () => {
    showInputType(button.dataset.type);
  });
});

input.addEventListener("input", () => {
  inputBuffers[inputType] = input.value;
});

combineChecks.forEach(checkbox => checkbox.addEventListener("change", updateCombination));
compactionChoices.forEach(choice => choice.addEventListener("change", updateCompactionMode));
environmentSource.addEventListener("change", renderEnvironment);
refreshEnvironment.addEventListener("click", requestEnvironmentRefresh);

document.querySelector("#clear-terminal").addEventListener("click", () => {
  terminal.innerHTML = "";
});

testedIntent.addEventListener("change", () => {
  const topic = topics.get(testedIntent.value);
  if (!topic) return;
  INPUT_ORDER.forEach(type => { inputBuffers[type] = topic.forms[type]?.content || ""; });
  const first = INPUT_ORDER.find(type => topic.forms[type]);
  combineChecks.forEach(checkbox => {
    checkbox.checked = checkbox.value === first;
    checkbox.disabled = !topic.forms[checkbox.value];
  });
  document.querySelectorAll("[data-type]").forEach(button => {
    button.disabled = !topic.forms[button.dataset.type];
  });
  showInputType(first, false);
  updateCombination();
  renderCatalogMeta(topic.forms[first]);
});

function selectedCatalogEntry() {
  const forms = topics.get(testedIntent.value)?.forms || {};
  return forms[inputType] || INPUT_ORDER.map(type => forms[type]).find(Boolean);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (source) source.close();
  inputBuffers[inputType] = input.value;
  const selected = combineChecks.filter(checkbox => checkbox.checked);
  if (!selected.length) {
    appendTerminal("Select at least one input for this run.", "error");
    return;
  }
  resetRun();
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        inputs: selected.map(checkbox => ({
          input_type: checkbox.value,
          content: inputBuffers[checkbox.value]
        })),
        environment_grants: selectedEnvironmentGrants(),
        environment_manifest: environmentSource.value === "fixture"
          ? selectedCatalogEntry()?.environment_manifest || null
          : null,
        compaction_mode: selectedCompactionMode(),
        llm: {
          foundry_project_endpoint: projectEndpoint.value,
          azure_openai_endpoint: apiEndpoint.value,
          model: azureModel.value
        }
      })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not start SkillC");
    source = new EventSource(`/api/runs/${payload.run_id}/events`);
    source.onmessage = event => handleEvent(JSON.parse(event.data));
    source.onerror = () => {
      if (runState.textContent === "RUNNING") finishRun("CONNECTION LOST", true);
    };
  } catch (error) {
    appendTerminal(error.message, "error");
    finishRun("ERROR", true);
  }
});

async function loadConfiguration() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    if (!response.ok) throw new Error(config.error || "Could not load app configuration");
    projectEndpoint.value = config.foundry_project_endpoint || "";
    apiEndpoint.value = config.azure_openai_endpoint || "";
    azureModel.value = config.model || "";
    azureAuth.textContent = `Authentication: ${config.authentication}`;
  } catch (error) {
    azureAuth.textContent = `Configuration error: ${error.message}`;
  }
}

function selectedCompactionMode() {
  return compactionChoices.find(choice => choice.checked).value;
}

function selectedEnvironmentGrants() {
  if (environmentSource.value === "fixture") {
    return selectedCatalogEntry()?.environment_grants || [];
  }
  return currentEnvironment?.grants || [];
}

function updateCompactionMode() {
  azureSettings.hidden = selectedCompactionMode() !== "azure-openai";
}

async function loadCatalog() {
  try {
    const response = await fetch("/api/intents");
    const catalog = await response.json();
    if (!response.ok) throw new Error(catalog.error || "Could not load tested intents");
    topics = new Map();
    catalog.entries.forEach(entry => {
      if (!topics.has(entry.base_id)) {
        topics.set(entry.base_id, {title: entry.name, suite: entry.suite, forms: {}});
      }
      topics.get(entry.base_id).forms[entry.input_type] = entry;
    });
    testedIntent.innerHTML = "";
    const suites = new Map();
    topics.forEach((topic, baseId) => {
      if (!suites.has(topic.suite)) suites.set(topic.suite, []);
      suites.get(topic.suite).push([baseId, topic]);
    });
    suites.forEach((members, suite) => {
      const group = document.createElement("optgroup");
      group.label = `${suite} (${members.length})`;
      members.forEach(([baseId, topic]) => {
        const option = document.createElement("option");
        option.value = baseId;
        option.textContent = topic.title;
        group.append(option);
      });
      testedIntent.append(group);
    });
    catalogCount.textContent = `${topics.size} tested · ${catalog.branch}`;
    if (topics.size) {
      testedIntent.value = topics.keys().next().value;
      testedIntent.dispatchEvent(new Event("change"));
    }
  } catch (error) {
    testedIntent.innerHTML = '<option value="">Catalog unavailable</option>';
    catalogCount.textContent = "load error";
    catalogMeta.innerHTML = `<span>${escapeHtml(error.message)}</span>`;
  }
}

async function loadEnvironment() {
  try {
    const response = await fetch("/api/environment");
    const snapshot = await response.json();
    if (!response.ok) throw new Error(snapshot.error || "Could not load environment");
    currentEnvironment = snapshot;
    renderEnvironment();
    if (snapshot.refreshing && !snapshot.captured_at) {
      setTimeout(loadEnvironment, 350);
    }
  } catch (error) {
    environmentMeta.textContent = `Environment discovery error: ${error.message}`;
  }
}

async function requestEnvironmentRefresh() {
  inputBuffers[inputType] = input.value;
  const contents = combineChecks
    .filter(checkbox => checkbox.checked)
    .map(checkbox => inputBuffers[checkbox.value]);
  refreshEnvironment.disabled = true;
  environmentMeta.textContent = "Refreshing the observed environment…";
  try {
    const response = await fetch("/api/environment/refresh", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({contents})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not refresh environment");
    await waitForEnvironmentRefresh();
  } catch (error) {
    environmentMeta.textContent = `Environment refresh error: ${error.message}`;
  } finally {
    refreshEnvironment.disabled = false;
  }
}

async function waitForEnvironmentRefresh() {
  for (;;) {
    await new Promise(resolve => setTimeout(resolve, 350));
    const response = await fetch("/api/environment");
    const snapshot = await response.json();
    if (!response.ok) throw new Error(snapshot.error || "Could not load environment");
    currentEnvironment = snapshot;
    renderEnvironment();
    if (!snapshot.refreshing) return;
  }
}

function renderEnvironment() {
  const fixture = selectedCatalogEntry()?.environment_grants || [];
  const usingFixture = environmentSource.value === "fixture";
  const grants = usingFixture ? fixture : currentEnvironment?.grants || [];
  const captured = currentEnvironment?.captured_at;
  if (usingFixture) {
    const manifest = selectedCatalogEntry()?.environment_manifest;
    environmentMeta.textContent = manifest
      ? `Topic environment · ${manifest.description} · ${grants.length} tools`
      : `Home runtime of this artifact · ${grants.length} tools · not a live probe`;
  } else if (currentEnvironment?.refreshing && !captured) {
    environmentMeta.textContent = "Discovering this coding environment for the first time…";
  } else if (currentEnvironment?.last_error) {
    environmentMeta.textContent =
      `Snapshot ${captured || "unavailable"} · ${currentEnvironment.last_error}`;
  } else {
    const schedule = currentEnvironment?.refresh_seconds
      ? `auto refresh every ${formatInterval(currentEnvironment.refresh_seconds)}`
      : "scheduled refresh disabled";
    environmentMeta.textContent =
      `Captured ${captured || "not yet"} · ${schedule} · ${grants.length} grants`;
  }
  discoveredGrants.replaceChildren(...(
    grants.length
      ? grants.map(grant => {
          const tag = document.createElement("span");
          tag.textContent = grant;
          return tag;
        })
      : [Object.assign(document.createElement("small"), {
          textContent: "No capabilities observed in this snapshot."
        })]
  ));
  if (runState.textContent !== "RUNNING") {
    runButton.disabled = !usingFixture && !captured;
  }
}

function formatInterval(seconds) {
  if (seconds % 3600 === 0) return `${seconds / 3600}h`;
  if (seconds % 60 === 0) return `${seconds / 60}m`;
  return `${seconds}s`;
}

function showInputType(type, preserveCurrent = true) {
  if (preserveCurrent) inputBuffers[inputType] = input.value;
  inputType = type;
  input.value = inputBuffers[type];
  document.querySelectorAll("[data-type]").forEach(button => {
    button.classList.toggle("selected", button.dataset.type === type);
  });
  updateCombination();
}

function updateCombination() {
  const selected = combineChecks.filter(checkbox => checkbox.checked);
  const count = selected.length;
  fileLabel.textContent = count > 1
    ? "COMPOSITE.md"
    : (
      selected.length
        ? {skill: "SKILL.md", agent: "agent.md", prompt: "prompt.md"}[selected[0].value]
        : "NO INPUT"
    );
  combineNote.textContent = count > 1
    ? `${count} sources · run as one composite`
    : `${count} source · run independently`;
}

function renderCatalogMeta(entry) {
  const fields = [
    {text: entry.suite},
    {text: entry.display_category || entry.category},
    {text: entry.form_provenance},
    {text: entry.source_path}
  ].filter(Boolean);
  catalogMeta.replaceChildren(...fields.map(field => {
    const badge = document.createElement("span");
    badge.textContent = field.text;
    if (field.className) badge.className = field.className;
    return badge;
  }));
  catalogMeta.title = entry.note || "";
  renderEnvironment();
}

function resetRun() {
  runButton.disabled = true;
  runState.textContent = "RUNNING";
  elapsed.textContent = "0 ms";
  terminal.innerHTML = "";
  functionsSeen = 0;
  selectedStage = "receive";
  stageArtifacts = new Map();
  stageModules = new Map();
  activeTraceStage = "receive";
  selectStage("receive");
  resetVerdictSummary();
  graphState.textContent = "RUNNING";
  renderEvidenceGraph();
}

function handleEvent(event) {
  if (typeof event.elapsed_ms === "number") elapsed.textContent = `${event.elapsed_ms} ms`;
  switch (event.type) {
    case "phase":
      activeTraceStage = event.id;
      activateStage(event.id);
      appendTerminal(`# ${event.label}: ${event.detail}`, "muted");
      break;
    case "module":
      addModule(event);
      break;
    case "artifact":
      stageArtifacts.set(event.stage, event);
      if (selectedStage === event.stage) renderGraphDetail();
      if (event.stage === "verdict") renderVerdictSummary(event.content);
      renderEvidenceGraph();
      break;
    case "explanation":
      verdictExplanationText.textContent = event.text;
      verdictExplanation.hidden = false;
      break;
    case "usage":
      renderTokenUsage(event);
      break;
    case "binding":
      appendTerminal(
        `environment grants: ${event.environment_grants.join(", ") || "(none)"}`,
        "muted"
      );
      appendTerminal(
        `required but unavailable: ${event.unavailable.join(", ") || "(none)"}`,
        event.unavailable.length ? "error" : "verdict"
      );
      break;
    case "command":
      appendTerminal(event.text, "command");
      break;
    case "terminal":
      appendTerminal(event.text, event.stream === "stderr" ? "error" : "");
      break;
    case "command_exit":
      appendTerminal(`[exit ${event.exit_code}]`, event.exit_code > 1 ? "error" : "muted");
      break;
    case "complete":
      finishRun(event.verdict || `EXIT ${event.exit_code}`, event.exit_code > 1);
      break;
  }
}

function renderVerdictSummary(verdict) {
  verdictLabel.textContent = verdict.verdict || "—";
  verdictLabel.className = `verdict-${(verdict.verdict || "").toLowerCase()}`;
  verdictReason.textContent = verdict.reason || "";
  const frontier = (verdict.frontier || []).join(", ");
  verdictDetail.textContent = [verdict.detail, frontier && `frontier: ${frontier}`]
    .filter(Boolean).join(" · ");
  verdictSummary.hidden = false;
}

function renderTokenUsage(event) {
  const rows = {...event.stages, total: event.total};
  tokenUsageRows.replaceChildren(...Object.entries(rows).map(([name, usage]) => {
    const row = document.createElement("tr");
    if (name === "total") row.className = "total";
    [name, usage.calls, usage.input_tokens, usage.cached_input_tokens,
      usage.output_tokens, usage.total_tokens].forEach(value => {
      const cell = document.createElement("td");
      cell.textContent = typeof value === "number" ? value.toLocaleString() : value;
      row.append(cell);
    });
    return row;
  }));
  tokenUsage.hidden = false;
  verdictSummary.hidden = false;
}

function resetVerdictSummary() {
  verdictSummary.hidden = true;
  verdictExplanation.hidden = true;
  tokenUsage.hidden = true;
  verdictExplanationText.textContent = "";
  tokenUsageRows.replaceChildren();
}

function activateStage(id) {
  selectStage(id);
}

function selectStage(id) {
  selectedStage = id;
  renderGraphDetail();
  renderEvidenceGraph();
}

function addModule(event) {
  const stage = inferModuleStage(event);
  if (!stageModules.has(stage)) stageModules.set(stage, []);
  stageModules.get(stage).push(event);
  functionsSeen += 1;
  if (selectedStage === stage) renderGraphDetail();
  renderEvidenceGraph();
}

function inferModuleStage(event) {
  const key = `${event.module}:${event.function}`;
  if (/frontend\/(markdown|prose|semantic)\.py/.test(key)) return "compile";
  if (/frontend\/grants\.py/.test(key)) return "bind";
  if (/session\.py/.test(key)) return "interaction";
  if (/checker\.py:(?:_reach|_goal_sat|_act|apply_effect|initial_state)/.test(key)) {
    return "reachability";
  }
  if (/checker\.py:(?:_missing_caps|_gamma_refutation|establishable_atoms)/.test(key)) {
    return "capability";
  }
  if (/pack\.py:(?:normalize|load|validate_pack|pack_digest)/.test(key)) return "schema";
  return activeTraceStage;
}

function renderEvidenceGraph() {
  const ns = "http://www.w3.org/2000/svg";
  evidenceGraph.replaceChildren();
  const defs = document.createElementNS(ns, "defs");
  const marker = document.createElementNS(ns, "marker");
  marker.setAttribute("id", "arrowhead");
  marker.setAttribute("markerWidth", "8");
  marker.setAttribute("markerHeight", "6");
  marker.setAttribute("refX", "7");
  marker.setAttribute("refY", "3");
  marker.setAttribute("orient", "auto");
  const arrow = document.createElementNS(ns, "path");
  arrow.setAttribute("d", "M0,0 L8,3 L0,6 Z");
  arrow.setAttribute("fill", "context-stroke");
  marker.append(arrow);
  defs.append(marker);
  evidenceGraph.append(defs);

  const labels = [];
  graphEdges.forEach(([from, to, label, fromSide, toSide]) => {
    const [x1, y1] = graphPort(graphStages[from], fromSide, 0);
    const [x2, y2] = graphPort(graphStages[to], toSide, 6);
    const reach = Math.min(160, Math.max(40, 0.45 * Math.hypot(x2 - x1, y2 - y1)));
    const [n1x, n1y] = SIDE_NORMALS[fromSide];
    const [n2x, n2y] = SIDE_NORMALS[toSide];
    const c1 = [x1 + n1x * reach, y1 + n1y * reach];
    const c2 = [x2 + n2x * reach, y2 + n2y * reach];
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", `M${x1},${y1} C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${x2},${y2}`);
    path.setAttribute("class", `graph-edge ${
      stageArtifacts.has(from) && stageArtifacts.has(to) ? "active" : ""
    }`);
    evidenceGraph.append(path);
    const midX = (x1 + 3 * c1[0] + 3 * c2[0] + x2) / 8;
    const midY = (y1 + 3 * c1[1] + 3 * c2[1] + y2) / 8;
    const horizontal = Math.abs(y1 - y2) < 1;
    const vertical = Math.abs(x1 - x2) < 1;
    labels.push({
      text: label,
      x: vertical ? midX + 12 : midX,
      y: horizontal ? midY - 12 : midY + 4,
      anchor: vertical ? "start" : "middle"
    });
  });

  Object.entries(graphStages).forEach(([id, stage]) => {
    const artifact = stageArtifacts.get(id);
    const status = graphNodeStatus(artifact);
    const group = document.createElementNS(ns, "g");
    group.setAttribute("class", `graph-node ${status} ${selectedStage === id ? "selected" : ""}`);
    group.setAttribute("transform", `translate(${stage.x} ${stage.y})`);
    group.setAttribute("role", "button");
    group.setAttribute("tabindex", "0");
    group.addEventListener("click", () => selectStage(id));
    group.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") selectStage(id);
    });
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("width", String(NODE_W));
    rect.setAttribute("height", String(NODE_H));
    rect.setAttribute("rx", "5");
    group.append(rect);
    group.append(svgText(ns, 12, 18, stage.kind, "node-kind"));
    group.append(svgText(ns, NODE_W - 12, 18, status.toUpperCase(), "node-status"));
    group.append(svgText(ns, 12, 41, stage.title, "node-title"));
    group.append(svgText(ns, 12, 61, artifactSummary(id, artifact), "node-output"));
    group.append(svgText(
      ns, 12, 76,
      `${(stageModules.get(id) || []).length} Python calls`,
      "node-output"
    ));
    evidenceGraph.append(group);
  });
  labels.forEach(label => {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", String(label.x));
    text.setAttribute("y", String(label.y));
    text.setAttribute("text-anchor", label.anchor);
    text.setAttribute("class", "graph-edge-label");
    text.textContent = label.text;
    evidenceGraph.append(text);
    const box = text.getBBox();
    const plate = document.createElementNS(ns, "rect");
    plate.setAttribute("x", String(box.x - 5));
    plate.setAttribute("y", String(box.y - 3));
    plate.setAttribute("width", String(box.width + 10));
    plate.setAttribute("height", String(box.height + 6));
    plate.setAttribute("rx", "3");
    plate.setAttribute("class", "graph-edge-plate");
    evidenceGraph.insertBefore(plate, text);
  });
  graphState.textContent = stageArtifacts.size
    ? `${stageArtifacts.size}/9 ARTIFACTS · SELECT A NODE`
    : "NO RUN YET";
}

function graphPort(stage, side, gap) {
  const [nx, ny] = SIDE_NORMALS[side];
  return [
    stage.x + NODE_W / 2 + nx * (NODE_W / 2 + gap),
    stage.y + NODE_H / 2 + ny * (NODE_H / 2 + gap)
  ];
}

function svgText(ns, x, y, text, className) {
  const node = document.createElementNS(ns, "text");
  node.setAttribute("x", String(x));
  node.setAttribute("y", String(y));
  node.setAttribute("class", className);
  node.textContent = text.length > 30 ? `${text.slice(0, 28)}…` : text;
  return node;
}

function graphNodeStatus(artifact) {
  if (!artifact) return "waiting";
  const status = artifact.content?.status;
  if (["passed", "refuted", "unknown", "skipped"].includes(status)) return status;
  if (artifact.stage === "verdict") {
    if (artifact.content?.verdict === "IMPOSSIBLE") return "refuted";
    if (artifact.content?.verdict === "UNKNOWN") return "unknown";
    if (artifact.content?.verdict === "ACHIEVABLE") return "passed";
  }
  return "complete";
}

function artifactSummary(id, artifact) {
  if (!artifact) return "waiting for output";
  const content = artifact.content || {};
  if (content.status) return content.status;
  if (id === "compile") return content.provenance?.goal_source || "pack emitted";
  if (id === "environment") return `${content.grant_count || 0} grants`;
  if (id === "bind") return `${content.unavailable_requirements?.length || 0} unavailable`;
  if (id === "verdict") return content.verdict || "decided";
  return "output ready";
}

function renderGraphDetail() {
  const stage = graphStages[selectedStage];
  const artifact = stageArtifacts.get(selectedStage);
  const modulesForStage = stageModules.get(selectedStage) || [];
  graphInputTitle.textContent = stage.input;
  graphInput.textContent = JSON.stringify(graphInputValue(selectedStage), null, 2);
  graphOutputTitle.textContent = artifact?.title || stage.output;
  graphOutput.textContent = artifact
    ? JSON.stringify(artifact.content, null, 2)
    : "This stage has not produced output in the current run.";
  graphCode.replaceChildren();
  const codeEvidence = modulesForStage.length
    ? modulesForStage
    : staticCodeEvidence(selectedStage);
  codeEvidence.forEach(item => {
    const row = document.createElement("div");
    row.className = "graph-code-item";
    const file = document.createElement("strong");
    file.textContent = item.module;
    const fn = document.createElement("span");
    fn.textContent = `${item.function}()${item.line ? ` · L${item.line}` : ""}`;
    row.append(file, fn);
    graphCode.append(row);
  });
  if (!codeEvidence.length) graphCode.textContent = "No Python calls captured for this stage.";
  graphEffect.textContent = stage.effect;
}

function graphInputValue(id) {
  if (id === "receive") return {source: "browser input buffers"};
  if (id === "compile") return stageArtifacts.get("receive")?.content || "Waiting for source";
  if (id === "environment") return {snapshot: ".skillc/env/latest.json"};
  if (id === "bind") return {
    requirement_pack: stageArtifacts.get("compile")?.content?.pack || "Waiting",
    environment: stageArtifacts.get("environment")?.content || "Waiting"
  };
  const predecessor = {
    schema: "bind", capability: "schema", interaction: "capability",
    reachability: "interaction", verdict: "reachability"
  }[id];
  return stageArtifacts.get(predecessor)?.content || `Waiting for ${predecessor}`;
}

function staticCodeEvidence(id) {
  const evidence = {
    receive: [
      {module: "demo/skillc-architecture-app/app.py", function: "_execute", line: 53},
      {module: "demo/skillc-architecture-app/composite_input.py", function: "build_source", line: 16}
    ],
    environment: [
      {module: "demo/skillc-architecture-app/environment_inventory.py", function: "snapshot", line: 40},
      {module: "src/skillc/env/claude.py", function: "probe", line: 68}
    ],
    verdict: [
      {module: "src/skillc/cli.py", function: "cmd_check", line: 156},
      {module: "src/skillc/checker.py", function: "check", line: 724}
    ]
  };
  return evidence[id] || [];
}

function appendTerminal(text, kind = "") {
  const line = document.createElement("span");
  line.className = kind ? `terminal-${kind}` : "";
  line.textContent = `${text}\n`;
  terminal.append(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function finishRun(verdict, failed = false) {
  if (source) source.close();
  source = null;
  runButton.disabled = false;
  runState.textContent = verdict;
  appendTerminal(`\n◆ ${verdict}`, failed ? "error" : "verdict");
  renderEvidenceGraph();
  graphState.textContent = `${verdict} · ${stageArtifacts.size}/9 ARTIFACTS`;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[character]);
}
