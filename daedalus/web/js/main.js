// DAEDALUS web app bootstrap: wiring of every panel, case management and shortcuts.
import { S, hooks, setLinks, typeInfo } from "./state.js";
import * as G from "./graph.js";
import { $, $$, api, debounce, esc, store, toast } from "./util.js";
import { L, t, applyI18n, getLang, setLang } from "./i18n.js";
import { iconSvg, uiIcon } from "./icons.js";
import { closeAll, cancelAll, renderProgress, runTransforms, runMachine } from "./jobs.js";
import { entityDialog, promptDialog, confirmDialog, settingsDialog, typeOptions, initSettingsTabs } from "./dialogs.js";
import { initInspector, renderInspector, renderTransforms, setInspectorTab } from "./inspector.js";
import { initMenu, nodeMenu, edgeMenu, canvasMenu, exportMenu, caseMenu, closeMenu } from "./menu.js";
import { initAriadne, initAnalysis, togglePanel, renderAnalysis, resetAriadne } from "./ariadne.js";
import { initTable, initTimeline, initNotes, renderView, clearMarks } from "./views.js";
import * as A from "./actions.js";

// ------------------------------------------------------------------ boot
async function boot() {
  for (const el of $$("i[data-ico]")) el.outerHTML = uiIcon(el.dataset.ico);
  const [meta, settings] = await Promise.all([api("/api/meta"), api("/api/settings")]);
  applyMeta(meta);
  S.settings = settings;
  setLang(settings.lang);
  if (S.settings.result_limit) S.limit = S.settings.result_limit;

  G.initGraph($("#cy"), {
    onSelection: () => hooks.selection(),
    onNodeMenu: (ev, ids) => nodeMenu(ev, ids),
    onEdgeMenu: (ev, data) => edgeMenu(ev, data),
    onCanvasMenu: (ev, pos) => canvasMenu(ev, pos),
    onNodeDbl: () => setInspectorTab("transforms"),
    onLinkTarget: (id) => A.finishLink(id).catch((e) => toast(e.message, "error")),
    onCanvasTap: () => {
      closeMenu();
      if ($("#ariadnePanel").classList.contains("hidden")) G.clearHighlight();
    },
  });
  $("#cy").addEventListener("contextmenu", (ev) => ev.preventDefault());
  window.DAEDALUS = { state: S, graph: G }; // handy from the devtools console

  hooks.selection = debounce(() => renderInspector(), 60);
  hooks.views = debounce(() => { renderView(); updateChrome(); }, 150);
  hooks.palette = debounce(renderPalette, 200);
  hooks.stale = debounce(() => { if (!$("#analysisPanel").classList.contains("hidden")) renderAnalysis(); }, 400);
  hooks.reload = () => S.caseId && openCase(S.caseId);
  hooks.openSettings = openSettings;

  initMenu();
  initSettingsTabs();
  initInspector();
  initAriadne();
  initAnalysis();
  initTable((ids) => A.deleteEntities(ids));
  initTimeline();
  initNotes();
  wireTopbar();
  wireToolbar();
  wirePalette();
  wireConsole();
  wireKeys();
  wireDrop();

  await loadCases();
  const last = store.get("lastCase", null);
  const target = S.cases.find((c) => c.id === last) || S.cases[0];
  if (target) await openCase(target.id);
  else await newCase(t("no_cases"));
}

function applyMeta(meta) {
  S.meta = meta;
  S.types = meta.entity_types;
  S.transforms = Object.fromEntries(meta.transforms.map((x) => [x.name, x]));
  S.machines = Object.fromEntries(meta.machines.map((x) => [x.name, x]));
}

// ----------------------------------------------------------------- cases
async function loadCases() {
  S.cases = await api("/api/cases");
  $("#caseSelect").innerHTML = S.cases.map((c) =>
    `<option value="${c.id}" ${c.id === S.caseId ? "selected" : ""}>${esc(c.name)} · ${c.entities}</option>`).join("");
}

async function openCase(id) {
  closeAll();
  const data = await api(`/api/cases/${id}`);
  S.caseId = id;
  S.case = data.case;
  S.entities = new Map(data.entities.map((e) => [e.id, e]));
  setLinks(data.links);
  S.runs = data.runs;
  S.selection = [];
  S.analysis = null;
  S.analysisStale = true;
  S.hiddenTypes.clear();
  A.cancelLinkMode();
  clearMarks();
  if (data.case.layout?.layoutName) {
    S.layoutName = data.case.layout.layoutName;
    $("#layoutSel").value = S.layoutName;
  }
  G.loadGraph(data.entities, data.links, data.case.layout);
  G.applyAnalysisStyle();
  resetAriadne();
  store.set("lastCase", id);
  $("#caseSelect").value = String(id);
  $("#notesArea").value = S.case.notes || "";
  renderInspector();
  renderPalette();
  renderAnalysis();
  renderProgress();
  hooks.views();
}

async function newCase(name) {
  const c = await api("/api/cases", { method: "POST", body: { name } });
  await loadCases();
  await openCase(c.id);
}

// ----------------------------------------------------------------- chrome
function updateChrome() {
  $("#emptyState").classList.toggle("hidden", S.entities.size > 0);
  $("#graphStats").textContent = t("case_summary", { e: S.entities.size, l: S.links.length });
  renderLegend();
  const opt = $(`#caseSelect option[value="${S.caseId}"]`);
  if (opt && S.case) opt.textContent = `${S.case.name} · ${S.entities.size}`;
}

function renderLegend() {
  const counts = {};
  for (const e of S.entities.values()) counts[e.type] = (counts[e.type] || 0) + 1;
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const box = $("#legend");
  box.classList.toggle("collapsed", !!store.get("legendCollapsed", true));
  box.innerHTML = rows.length ? `<div class="lg-head" data-toggle="1"><span>${esc(t("types"))}</span>${uiIcon(box.classList.contains("collapsed") ? "right" : "down", 12)}</div>`
    + rows.map(([type, n]) => {
      const info = typeInfo(type);
      return `<div class="lg-row ${S.hiddenTypes.has(type) ? "off" : ""}" data-type="${esc(type)}">
        <span class="dot" style="background:${info.color}"></span>${esc(L(info.label))}<span class="n">${n}</span></div>`;
    }).join("") : "";
}

function renderPalette() {
  const q = $("#paletteFilter").value.trim().toLowerCase();
  const counts = {};
  for (const e of S.entities.values()) counts[e.type] = (counts[e.type] || 0) + 1;
  const byCat = {};
  for (const [key, info] of Object.entries(S.types)) {
    if (!info.manual) continue;
    if (q && !`${L(info.label)} ${key}`.toLowerCase().includes(q)) continue;
    (byCat[info.category] ||= []).push([key, info]);
  }
  $("#paletteList").innerHTML = Object.entries(byCat).map(([cat, items]) => `<div class="pal-cat">
    <div class="cat-name">${esc(L(S.meta.entity_categories[cat]))}</div>
    ${items.map(([key, info]) => `<div class="pal-item" draggable="true" data-type="${esc(key)}" title="${esc(L(info.label))}">
      <span class="ico" style="color:${info.color}">${iconSvg(key, info.color, 14)}</span>
      <span class="name">${esc(L(info.label))}</span><span class="count">${counts[key] || ""}</span></div>`).join("")}
  </div>`).join("");
  $("#machineList").innerHTML = Object.values(S.machines).map((m) => `<div class="machine-item" data-machine="${esc(m.name)}" title="${esc(L(m.description))}">
    <b>${uiIcon("cpu", 13)}${esc(L(m.title))}</b><span>${esc(L(m.description))}</span></div>`).join("");
}

function fillQuickType(detected = null) {
  const sel = $("#quickType");
  const cur = sel.value;
  sel.innerHTML = typeOptions(cur, { manualOnly: true, auto: true });
  sel.options[0].textContent = detected ? `${t("auto")} · ${L(typeInfo(detected).label)}` : t("auto");
  sel.value = cur;
}

const otherLang = () => (getLang() === "en" ? "es" : "en");

function refreshLanguage() {
  applyI18n();
  $("#langBtn").textContent = otherLang().toUpperCase();
  fillQuickType();
  renderPalette();
  renderInspector();
  renderAnalysis();
  G.relabelEdges();
  hooks.views();
}

async function changeLanguage(lang) {
  S.settings = await api("/api/settings", { method: "PUT", body: { lang } });
  setLang(S.settings.lang);
  refreshLanguage();
}

// Settings dialog; reacts to what changed (language, API keys unlocking transforms)
async function openSettings(tab = "general") {
  const before = getLang();
  const saved = await settingsDialog(tab);
  if (!saved) return;
  applyMeta(await api("/api/meta"));
  if (saved.lang !== before) {
    setLang(saved.lang);
    refreshLanguage();
  } else {
    renderInspector();
  }
  toast(t("saved"), "ok");
}

// ----------------------------------------------------------------- wiring
function wireTopbar() {
  $("#langBtn").textContent = otherLang().toUpperCase();
  $("#langBtn").addEventListener("click", () => changeLanguage(otherLang()).catch((e) => toast(e.message, "error")));
  $("#caseSelect").addEventListener("change", (ev) => openCase(Number(ev.target.value)).catch((e) => toast(e.message, "error")));
  $("#newCaseBtn").addEventListener("click", async () => {
    const name = await promptDialog({ title: t("new_case").replace("+", "").trim(), text: t("case_name"), ok: t("create") });
    if (name) await newCase(name);
  });
  $("#caseMenuBtn").addEventListener("click", (ev) => caseMenu(ev, {
    rename: async () => {
      const name = await promptDialog({ title: t("rename_case"), value: S.case.name, ok: t("save") });
      if (!name) return;
      S.case = await api(`/api/cases/${S.caseId}`, { method: "PATCH", body: { name } });
      await loadCases();
    },
    remove: async () => {
      if (!(await confirmDialog(t("delete_case"), t("confirm_delete_case", { name: S.case.name })))) return;
      await api(`/api/cases/${S.caseId}`, { method: "DELETE" });
      S.caseId = null;
      await loadCases();
      if (S.cases.length) await openCase(S.cases[0].id);
      else await newCase(t("no_cases"));
    },
  }));
  $("#settingsBtn").addEventListener("click", () => openSettings().catch((e) => toast(e.message, "error")));
  $("#exportBtn").addEventListener("click", (ev) => exportMenu(ev));
  $("#importBtn").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const c = await api("/api/import", { method: "POST", form: fd });
      await loadCases();
      await openCase(c.id);
      toast(t("imported"), "ok");
    } catch (e) { toast(e.message, "error"); }
  });

  fillQuickType();
  const detect = debounce(async () => {
    const v = $("#quickInput").value.trim();
    if (!v) return fillQuickType();
    try { fillQuickType((await api("/api/detect", { method: "POST", body: { value: v } })).type); } catch { /* offline */ }
  }, 250);
  $("#quickInput").addEventListener("input", detect);
  const quickAdd = async (run) => {
    const value = $("#quickInput").value.trim();
    if (!value) {
      toast(t("value_required"));
      return;
    }
    try {
      const ent = await A.createEntity({ type: $("#quickType").value || null, value });
      $("#quickInput").value = "";
      fillQuickType();
      toast(t("added", { label: ent.label }), "ok");
      if (run) await runTransforms([ent.id], null);
    } catch (e) { toast(e.message, "error"); }
  };
  $("#quickAdd").addEventListener("submit", (ev) => { ev.preventDefault(); quickAdd(false); });
  $("#quickRun").addEventListener("click", () => quickAdd(true));
}

function wireToolbar() {
  $$(".toolbar .tab").forEach((b) => b.addEventListener("click", () => {
    S.tab = b.dataset.tab;
    $$(".toolbar .tab").forEach((x) => x.classList.toggle("active", x === b));
    for (const v of ["graph", "table", "map", "timeline", "notes"]) $(`#${v}View`).classList.toggle("hidden", v !== S.tab);
    $("#graphTools").style.visibility = S.tab === "graph" ? "visible" : "hidden";
    if (S.tab === "graph") G.cy.resize();
    renderView();
  }));
  $("#layoutSel").value = S.layoutName;
  $("#layoutSel").addEventListener("change", (ev) => {
    S.layoutName = ev.target.value;
    store.set("layoutName", S.layoutName);
    G.runLayout(S.layoutName, { randomize: S.layoutName === "organic" });
  });
  $("#layoutBtn").addEventListener("click", () => G.runLayout(S.layoutName, { randomize: true }));
  $("#autoLayout").checked = S.autoLayout;
  $("#autoLayout").addEventListener("change", (ev) => { S.autoLayout = ev.target.checked; store.set("autoLayout", S.autoLayout); });
  $("#ariadneBtn").addEventListener("click", () => togglePanel("ariadnePanel"));
  $("#analysisBtn").addEventListener("click", () => togglePanel("analysisPanel"));
  $("#edgeLabels").addEventListener("change", (ev) => G.setEdgeLabels(ev.target.checked));
  let hits = [];
  let hitIdx = 0;
  $("#graphSearch").addEventListener("input", debounce((ev) => { hits = G.searchGraph(ev.target.value); hitIdx = 0; }, 150));
  $("#graphSearch").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && hits.length) {
      G.selectIds([hits[hitIdx % hits.length]], { center: true });
      hitIdx++;
    }
    if (ev.key === "Escape") { ev.target.value = ""; G.searchGraph(""); }
  });
  $("#zoomIn").addEventListener("click", () => G.zoomBy(1.25));
  $("#zoomOut").addEventListener("click", () => G.zoomBy(0.8));
  $("#fitBtn").addEventListener("click", () => G.fit());
  $("#pngBtn").addEventListener("click", () => G.exportPng(`daedalus_${(S.case?.name || "case").replace(/\W+/g, "_")}`));
  $("#legend").addEventListener("click", (ev) => {
    if (ev.target.closest("[data-toggle]")) {
      store.set("legendCollapsed", !$("#legend").classList.contains("collapsed"));
      renderLegend();
      return;
    }
    const chip = ev.target.closest("[data-type]");
    if (!chip) return;
    const type = chip.dataset.type;
    if (S.hiddenTypes.has(type)) S.hiddenTypes.delete(type);
    else S.hiddenTypes.add(type);
    G.applyTypeVisibility();
    renderLegend();
  });
}

// narrow windows fold the palette into its icon rail without overwriting the saved preference
const narrow = matchMedia("(max-width: 1100px)");

function setPaletteCollapsed(on, remember = true) {
  $("#palette").classList.toggle("collapsed", on);
  $("#workspace").classList.toggle("palette-collapsed", on);
  const btn = $("#paletteToggle");
  btn.innerHTML = uiIcon(on ? "expand" : "collapse");
  btn.dataset.i18nTitle = on ? "palette_expand" : "palette_collapse";
  btn.title = t(btn.dataset.i18nTitle);
  if (remember) store.set("paletteCollapsed", on);
}

function wirePalette() {
  const fromPrefs = () => setPaletteCollapsed(narrow.matches || !!store.get("paletteCollapsed", false), false);
  fromPrefs();
  narrow.addEventListener("change", fromPrefs);
  $("#paletteToggle").addEventListener("click", () => {
    const on = !$("#palette").classList.contains("collapsed");
    setPaletteCollapsed(on, !narrow.matches);
  });
  $("#paletteFilter").addEventListener("input", debounce(renderPalette, 120));
  $("#paletteList").addEventListener("dragstart", (ev) => {
    const item = ev.target.closest("[data-type]");
    if (!item) return;
    ev.dataTransfer.setData("application/x-daedalus-type", item.dataset.type);
    ev.dataTransfer.effectAllowed = "copy";
  });
  $("#paletteList").addEventListener("click", async (ev) => {
    const item = ev.target.closest("[data-type]");
    if (!item) return;
    const r = await entityDialog({ type: item.dataset.type });
    if (r) await A.createEntity(r).catch((e) => toast(e.message, "error"));
  });
  $("#machineList").addEventListener("click", (ev) => {
    const item = ev.target.closest("[data-machine]");
    if (!item) return;
    if (!S.selection.length) {
      toast(t("nothing_selected"));
      return;
    }
    runMachine([...S.selection], item.dataset.machine, 2).catch((e) => toast(e.message, "error"));
  });
  $("#imageInput").addEventListener("change", (ev) => {
    const f = ev.target.files[0];
    ev.target.value = "";
    if (f) uploadImage(f);
  });
}

async function uploadImage(file) {
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await api(`/api/cases/${S.caseId}/upload`, { method: "POST", form: fd });
    await openCase(S.caseId);
    G.selectIds([r.entity.id], { center: true });
    toast(t("image_uploaded"), "ok");
  } catch (e) { toast(e.message, "error"); }
}

function wireDrop() {
  const view = $("#graphView");
  let hint = null;
  const showHint = (on) => {
    if (on && !hint) {
      hint = document.createElement("div");
      hint.className = "drop-hint";
      view.append(hint);
    } else if (!on && hint) {
      hint.remove();
      hint = null;
    }
  };
  view.addEventListener("dragover", (ev) => {
    const types = [...ev.dataTransfer.types];
    if (types.includes("application/x-daedalus-type") || types.includes("Files")) {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
      showHint(true);
    }
  });
  view.addEventListener("dragleave", (ev) => { if (!view.contains(ev.relatedTarget)) showHint(false); });
  view.addEventListener("drop", async (ev) => {
    showHint(false);
    const type = ev.dataTransfer.getData("application/x-daedalus-type");
    if (type) {
      ev.preventDefault();
      const rect = $("#cy").getBoundingClientRect();
      const pos = G.renderedToModel(ev.clientX - rect.left, ev.clientY - rect.top);
      const r = await entityDialog({ type });
      if (r) await A.createEntity({ ...r, position: pos }).catch((e) => toast(e.message, "error"));
      return;
    }
    const file = ev.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      ev.preventDefault();
      uploadImage(file);
    }
  });
}

function setConsoleCollapsed(on) {
  $("#console").classList.toggle("collapsed", on);
  $("#toggleConsole").innerHTML = uiIcon(on ? "up" : "down");
}

function wireConsole() {
  const c = $("#console");
  const MIN = 60;
  const maxHeight = () => Math.max(MIN, c.parentElement.clientHeight - 160);
  const saved = store.get("consoleHeight", null);
  if (saved) c.style.height = `${Math.min(saved, maxHeight())}px`;
  $("#toggleConsole").addEventListener("click", () => setConsoleCollapsed(!c.classList.contains("collapsed")));

  // drag the top edge to resize; dragging below the minimum collapses it
  const grip = $("#consoleResize");
  grip.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    grip.setPointerCapture(ev.pointerId);
    const startY = ev.clientY;
    const startH = c.getBoundingClientRect().height;
    document.body.classList.add("resizing-v");
    const move = (e) => {
      const h = startH + (startY - e.clientY);
      if (h < MIN / 2) {
        setConsoleCollapsed(true);
        return;
      }
      setConsoleCollapsed(false);
      c.style.height = `${Math.min(Math.max(h, MIN), maxHeight())}px`;
    };
    const up = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", up);
      grip.removeEventListener("pointercancel", up);
      document.body.classList.remove("resizing-v");
      if (!c.classList.contains("collapsed")) store.set("consoleHeight", Math.round(c.getBoundingClientRect().height));
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", up);
    grip.addEventListener("pointercancel", up);
  });
  grip.addEventListener("dblclick", () => {
    c.style.height = "";
    store.set("consoleHeight", null);
    setConsoleCollapsed(false);
  });
  window.addEventListener("resize", () => {
    if (c.style.height && parseFloat(c.style.height) > maxHeight()) c.style.height = `${maxHeight()}px`;
  });
  $("#clearLog").addEventListener("click", () => { $("#log").innerHTML = ""; });
  $("#cancelJobs").addEventListener("click", () => cancelAll());
  $("#log").addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-id]");
    if (el) G.selectIds([el.dataset.id], { center: true });
  });
}

function wireKeys() {
  // Delete/Backspace only remove entities right after working in the graph, never because focus slipped out of a field
  let inGraph = false;
  document.addEventListener("pointerdown", (ev) => {
    if (!ev.target.closest("dialog, #ctxMenu")) inGraph = !!ev.target.closest("#cy");
  }, true);
  document.addEventListener("keydown", (ev) => {
    const typing = ev.target.closest("input, textarea, select, [contenteditable]") || document.querySelector("dialog[open]");
    if (ev.key === "Escape") {
      closeMenu();
      if (S.linkFrom) A.cancelLinkMode();
      if (!typing) {
        G.clearHighlight();
        G.cy.nodes().unselect();
      }
      return;
    }
    if (typing || S.tab !== "graph") return;
    if ((ev.key === "Delete" || ev.key === "Backspace") && S.selection.length && inGraph) {
      ev.preventDefault();
      A.deleteEntities([...S.selection], { ask: S.selection.length > 1 }).catch((e) => toast(e.message, "error"));
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "a") {
      ev.preventDefault();
      G.cy.nodes(":visible").select();
    } else if (ev.key.toLowerCase() === "f" && !ev.ctrlKey && !ev.metaKey) {
      G.fit();
    }
  });
}

boot().catch((e) => {
  console.error(e);
  toast(`DAEDALUS: ${e.message}`, "error");
});

export { renderTransforms };
