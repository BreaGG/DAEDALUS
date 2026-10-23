// Ariadne's thread (path finding) and the structural analysis panel.
import { S, typeInfo } from "./state.js";
import * as G from "./graph.js";
import { $, api, esc, short, toast } from "./util.js";
import { L, t, linkLabel } from "./i18n.js";
import { iconSvg } from "./icons.js";
import * as A from "./actions.js";

const chip = (id) => {
  const e = S.entities.get(id);
  if (!e) return `<span class="chip">?</span>`;
  const info = typeInfo(e.type);
  return `<span class="chip click" data-goto="${esc(id)}" title="${esc(e.value)}">${iconSvg(e.type, info.color, 12)} ${esc(short(e.label, 26))}</span>`;
};

export function togglePanel(id, force) {
  const el = $(`#${id}`);
  const show = force ?? el.classList.contains("hidden");
  for (const other of ["ariadnePanel", "analysisPanel"]) if (other !== id && show) $(`#${other}`).classList.add("hidden");
  el.classList.toggle("hidden", !show);
  $("#ariadneBtn").classList.toggle("active", !$("#ariadnePanel").classList.contains("hidden"));
  $("#analysisBtn").classList.toggle("active", !$("#analysisPanel").classList.contains("hidden"));
  if (id === "analysisPanel" && show) renderAnalysis();
  if (id === "ariadnePanel" && show) renderSlots();
}

// ------------------------------------------------------------------ Ariadne
export function setEnd(which, id) {
  S.ariadne[which] = id;
  togglePanel("ariadnePanel", true);
  renderSlots();
  if (S.ariadne.src && S.ariadne.dst) findPaths();
}

function renderSlots() {
  for (const [which, el] of [["src", "#ariSrc"], ["dst", "#ariDst"]]) {
    const id = S.ariadne[which];
    $(el).innerHTML = id && S.entities.has(id) ? chip(id) : `<span>${esc(t("use_selection"))} ⊙</span>`;
    $(el).classList.toggle("filled", !!id);
  }
}

export async function findPaths() {
  const { src, dst } = S.ariadne;
  if (!src || !dst) {
    toast(t("pick_two"));
    return;
  }
  const body = { src, dst, k: Number($("#ariK").value) || 5, max_len: Number($("#ariMax").value) || null,
    directed: $("#ariDirected").checked };
  const r = await api(`/api/cases/${S.caseId}/paths`, { method: "POST", body });
  S.ariadne.paths = r.paths;
  S.ariadne.active = r.paths.length ? 0 : -1;
  renderResults();
  if (r.paths.length) G.highlightPath(r.paths[0].nodes);
  else G.clearHighlight();
}

function renderResults() {
  const box = $("#ariResults");
  const paths = S.ariadne.paths;
  if (!paths.length) {
    box.innerHTML = S.ariadne.src && S.ariadne.dst ? `<div class="muted small">${esc(t("no_path"))}</div>` : "";
    return;
  }
  box.innerHTML = `<div class="field-row"><span class="section-label" style="flex:1">${esc(t("paths_found", { n: paths.length }))}</span>
      <button class="btn sm ghost" data-all="1">${esc(t("show_all"))}</button></div>`
    + paths.map((p, i) => `<div class="path-card ${i === S.ariadne.active ? "active" : ""}" data-path="${i}">
      <div class="meta"><span>#${i + 1}</span><span>${esc(t("hops", { n: p.length }))}</span></div>
      <div class="chain">${p.nodes.map((n, j) => {
        const hop = p.hops[j];
        const arrow = hop ? `<span class="hop">${hop.forward ? "" : "←"}${esc(linkLabel(hop.labels[0] || ""))}${hop.forward ? "→" : ""}</span>` : "";
        return chip(n) + arrow;
      }).join("")}</div></div>`).join("");
}

export async function connectSelection() {
  const ids = [...S.selection];
  if (ids.length < 2) {
    toast(t("connect_help"));
    return;
  }
  const r = await api(`/api/cases/${S.caseId}/connect`, { method: "POST", body: { ids, directed: false } });
  G.highlight(r.nodes, r.edges, ids);
  if (r.unreachable.length) toast(t("unreachable_pairs", { n: r.unreachable.length }));
}

export function initAriadne() {
  $("#ariSrcBtn").addEventListener("click", () => { if (S.selection[0]) setEnd("src", S.selection[0]); });
  $("#ariDstBtn").addEventListener("click", () => {
    const id = S.selection[S.selection.length - 1];
    if (id) setEnd("dst", id);
  });
  $("#ariSwap").addEventListener("click", () => {
    S.ariadne = { ...S.ariadne, src: S.ariadne.dst, dst: S.ariadne.src };
    renderSlots();
    if (S.ariadne.src && S.ariadne.dst) findPaths().catch((e) => toast(e.message, "error"));
  });
  $("#ariFind").addEventListener("click", () => findPaths().catch((e) => toast(e.message, "error")));
  $("#ariClear").addEventListener("click", () => {
    S.ariadne = { src: null, dst: null, paths: [], active: -1 };
    renderSlots();
    renderResults();
    G.clearHighlight();
  });
  $("#ariConnect").addEventListener("click", () => connectSelection().catch((e) => toast(e.message, "error")));
  $("#ariResults").addEventListener("click", (ev) => {
    const go = ev.target.closest("[data-goto]");
    if (go) {
      G.centerOn(go.dataset.goto);
      return;
    }
    if (ev.target.closest("[data-all]")) {
      const nodes = [...new Set(S.ariadne.paths.flatMap((p) => p.nodes))];
      const pairs = S.ariadne.paths.flatMap((p) => p.nodes.slice(1).map((n, i) => [p.nodes[i], n]));
      G.highlight(nodes, pairs, [S.ariadne.src, S.ariadne.dst]);
      S.ariadne.active = -1;
      renderResults();
      return;
    }
    const card = ev.target.closest("[data-path]");
    if (card) {
      S.ariadne.active = Number(card.dataset.path);
      G.highlightPath(S.ariadne.paths[S.ariadne.active].nodes);
      renderResults();
    }
  });
  for (const id of ["ariSrc", "ariDst"]) {
    $(`#${id}`).addEventListener("click", (ev) => {
      const go = ev.target.closest("[data-goto]");
      if (go) G.centerOn(go.dataset.goto);
    });
  }
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => {
    togglePanel(b.dataset.close, false);
    G.clearHighlight();
  }));
}

export function resetAriadne() {
  S.ariadne = { src: null, dst: null, paths: [], active: -1 };
  renderSlots();
  renderResults();
}

// ----------------------------------------------------------------- analysis
export async function computeAnalysis() {
  S.analysis = await api(`/api/cases/${S.caseId}/analysis`);
  S.analysisStale = false;
  G.applyAnalysisStyle();
  renderAnalysis();
}

const rankRow = (id, val, max, fmt = (v) => v) => {
  const e = S.entities.get(id);
  if (!e) return "";
  const info = typeInfo(e.type);
  return `<div class="rank-row" data-goto="${esc(id)}"><span style="color:${info.color}">${iconSvg(e.type, info.color, 13)}</span>
    <span class="lbl" title="${esc(e.value)}">${esc(e.label)}</span>
    <span class="bar" style="width:${Math.max(4, Math.round(60 * (max ? val / max : 0)))}px"></span><span class="val">${fmt(val)}</span></div>`;
};

export function renderAnalysis() {
  const body = $("#analysisBody");
  const a = S.analysis;
  if (!a) {
    body.innerHTML = `<div class="muted small">${esc(t("analysis_empty"))}</div>`;
    return;
  }
  const s = a.stats;
  const opt = (v, cur, key) => `<option value="${v}" ${v === cur ? "selected" : ""}>${esc(t(key))}</option>`;
  const maxB = Math.max(...a.hubs.map((h) => h.betweenness), 0);
  body.innerHTML = `
    ${S.analysisStale ? `<div class="small" style="color:var(--warn)">${esc(t("analysis_stale"))}</div>` : ""}
    <div class="stats-grid">
      <div class="stat-box"><b>${s.entities}</b><span>${esc(t("an_entities"))}</span></div>
      <div class="stat-box"><b>${s.links}</b><span>${esc(t("an_links"))}</span></div>
      <div class="stat-box"><b>${s.components}</b><span>${esc(t("an_components"))}</span></div>
      <div class="stat-box"><b>${s.communities}</b><span>${esc(t("an_communities"))}</span></div>
      <div class="stat-box"><b>${s.modularity}</b><span>${esc(t("an_modularity"))}</span></div>
      <div class="stat-box"><b>${s.density}</b><span>${esc(t("an_density"))}</span></div>
    </div>
    <div class="opts">
      <label>${esc(t("size_by"))}<select id="anSize">${opt("none", S.sizeBy, "m_none")}${opt("degree", S.sizeBy, "m_degree")}
        ${opt("betweenness", S.sizeBy, "m_betweenness")}${opt("pagerank", S.sizeBy, "m_pagerank")}</select></label>
      <label>${esc(t("color_by"))}<select id="anColor">${opt("type", S.colorBy, "c_type")}${opt("community", S.colorBy, "c_community")}
        ${opt("component", S.colorBy, "c_component")}</select></label>
    </div>
    <label class="check small"><input type="checkbox" id="anChoke" ${S.showChoke ? "checked" : ""}> ${esc(t("show_choke"))}</label>
    <div class="section-label">${esc(t("hubs"))}</div>
    <div class="rank-list">${a.hubs.map((h) => rankRow(h.id, h.betweenness, maxB, (v) => v.toFixed(3))).join("") || `<div class="muted small">${esc(t("none_found"))}</div>`}</div>
    <div class="section-label">${esc(t("choke_points"))} · ${a.articulation_points.length}</div>
    <div class="muted small">${esc(t("choke_help"))}</div>
    <div class="rank-list">${a.articulation_points.slice(0, 15).map((id) => rankRow(id, a.degree[id], 0, (v) => `${v}`)).join("")
      || `<div class="muted small">${esc(t("none_found"))}</div>`}</div>
    <div class="section-label">${esc(t("similar_pairs"))}</div>
    <div class="muted small">${esc(t("similar_help"))}</div>
    <div class="rank-list">${a.similar.map((p, i) => {
      const ea = S.entities.get(p.a);
      const eb = S.entities.get(p.b);
      if (!ea || !eb) return "";
      return `<div class="rank-row" data-pair="${i}"><span class="lbl">${esc(short(ea.label, 18))} ⇄ ${esc(short(eb.label, 18))}</span>
        <span class="val">${esc(t("shared", { n: p.shared.length }))}</span><button class="btn sm ghost" data-merge="${i}">${esc(t("merge"))}</button></div>`;
    }).join("") || `<div class="muted small">${esc(t("none_found"))}</div>`}</div>`;
}

export function initAnalysis() {
  $("#anRefresh").addEventListener("click", () => computeAnalysis().catch((e) => toast(e.message, "error")));
  const body = $("#analysisBody");
  body.addEventListener("change", (ev) => {
    if (ev.target.id === "anSize") S.sizeBy = ev.target.value;
    if (ev.target.id === "anColor") S.colorBy = ev.target.value;
    if (ev.target.id === "anChoke") S.showChoke = ev.target.checked;
    G.applyAnalysisStyle();
  });
  body.addEventListener("click", (ev) => {
    const merge = ev.target.closest("[data-merge]");
    if (merge) {
      const p = S.analysis.similar[Number(merge.dataset.merge)];
      A.mergeEntities([p.a, p.b]).then(() => computeAnalysis()).catch((e) => toast(e.message, "error"));
      return;
    }
    const pair = ev.target.closest("[data-pair]");
    if (pair) {
      const p = S.analysis.similar[Number(pair.dataset.pair)];
      G.highlight([p.a, p.b, ...p.shared], p.shared.flatMap((m) => [[p.a, m], [p.b, m]]), [p.a, p.b]);
      return;
    }
    const go = ev.target.closest("[data-goto]");
    if (go) {
      G.selectIds([go.dataset.goto], { center: true });
    }
  });
}

export const labelOf = (id) => L(typeInfo(S.entities.get(id)?.type).label);
