// Context menus for nodes, links, the canvas, export and case actions.
import { S, hooks, typeInfo, transformsFor, machinesFor, BOOKMARK_COLORS } from "./state.js";
import * as G from "./graph.js";
import { $, api, esc, safeUrl, short, toast } from "./util.js";
import { L, t } from "./i18n.js";
import { iconSvg } from "./icons.js";
import { runTransforms, runMachine } from "./jobs.js";
import { entityDialog } from "./dialogs.js";
import * as A from "./actions.js";
import { setEnd, connectSelection } from "./ariadne.js";

let actions = [];

function renderItems(items) {
  return items.map((it) => {
    if (it.sep) return '<div class="ctx-sep"></div>';
    if (it.group) return `<div class="ctx-group">${esc(it.group)}</div>`;
    const idx = actions.push(it.action || null) - 1;
    const sub = it.sub && it.sub.length ? `<div class="ctx-sub">${renderItems(it.sub)}</div>` : "";
    return `<div class="ctx-item ${it.disabled ? "disabled" : ""} ${it.danger ? "danger" : ""}" data-idx="${idx}" ${it.title ? `title="${esc(it.title)}"` : ""}>
      <span style="width:16px;text-align:center">${it.icon || ""}</span><span class="lbl">${esc(it.label)}</span>
      ${it.hint ? `<span class="hint">${esc(it.hint)}</span>` : ""}${sub ? '<span class="arrow">▸</span>' : ""}${sub}</div>`;
  }).join("");
}

export function openMenu(ev, { head = "", items }) {
  const m = $("#ctxMenu");
  actions = [];
  m.innerHTML = (head ? `<div class="ctx-head">${head}</div>` : "") + renderItems(items);
  m.classList.remove("hidden", "flip");
  m.style.left = "0px";
  m.style.top = "0px";
  const r = m.getBoundingClientRect();
  const x = ev?.clientX ?? innerWidth / 2;
  const y = ev?.clientY ?? innerHeight / 2;
  const left = Math.max(6, Math.min(x, innerWidth - r.width - 6));
  m.style.left = `${left}px`;
  m.style.top = `${Math.max(6, Math.min(y, innerHeight - r.height - 6))}px`;
  if (left + r.width + 270 > innerWidth) m.classList.add("flip");
}

export function closeMenu() {
  $("#ctxMenu").classList.add("hidden");
}

export function initMenu() {
  const m = $("#ctxMenu");
  m.addEventListener("click", (ev) => {
    const el = ev.target.closest(".ctx-item");
    if (!el || el.classList.contains("disabled")) return;
    const fn = actions[Number(el.dataset.idx)];
    if (!fn) return;
    closeMenu();
    Promise.resolve().then(fn).catch((e) => { console.error(e); toast(e.message, "error"); });
  });
  m.addEventListener("mouseover", (ev) => {
    const item = ev.target.closest(".ctx-item");
    const sub = item && item.querySelector(":scope > .ctx-sub");
    if (!sub) return;
    sub.style.top = "-6px";
    requestAnimationFrame(() => {
      const r = sub.getBoundingClientRect();
      if (r.bottom > innerHeight - 6) sub.style.top = `${-6 - (r.bottom - innerHeight + 10)}px`;
    });
  });
  document.addEventListener("mousedown", (ev) => { if (!ev.target.closest("#ctxMenu")) closeMenu(); });
  window.addEventListener("blur", closeMenu);
  window.addEventListener("resize", closeMenu);
  m.addEventListener("contextmenu", (ev) => ev.preventDefault());
}

const head = (e) => {
  const info = typeInfo(e.type);
  return `<span style="color:${info.color}">${iconSvg(e.type, info.color, 16)}</span><span class="lbl">${esc(e.label)}</span>`;
};

function transformItems(ids, types) {
  const list = transformsFor(types);
  const byCat = {};
  for (const tr of list) (byCat[tr.category] ||= []).push(tr);
  return Object.entries(byCat).map(([cat, items]) => ({
    label: L(S.meta.transform_categories[cat]) || cat,
    icon: "›",
    sub: items.map((tr) => ({
      label: L(tr.title),
      title: L(tr.description),
      hint: tr.ready ? "" : `🔑 ${tr.keys.join(", ")}`,
      action: tr.ready ? () => runTransforms(ids, [tr.name]) : () => hooks.openSettings("keys"),
    })),
  }));
}

export function nodeMenu(ev, ids) {
  const ents = ids.map((id) => S.entities.get(id)).filter(Boolean);
  if (!ents.length) return;
  const types = [...new Set(ents.map((e) => e.type))];
  const single = ents.length === 1 ? ents[0] : null;
  const nDefault = transformsFor(types).filter((x) => x.default).length;
  const machines = machinesFor(types);
  const items = [
    { label: t("run_all_n", { n: nDefault }), icon: "▶", action: () => runTransforms(ids, null), disabled: !nDefault },
    ...transformItems(ids, types),
  ];
  if (machines.length) {
    items.push({ label: t("machines_menu"), icon: "⚙", sub: machines.map((m) => ({
      label: L(m.title), title: L(m.description), action: () => runMachine(ids, m.name, 2) })) });
  }
  items.push({ sep: true });
  if (single) {
    items.push({ label: t("ari_from"), icon: "🧵", action: () => setEnd("src", single.id) });
    items.push({ label: t("ari_to"), icon: "◎", action: () => setEnd("dst", single.id) });
  } else {
    items.push({ label: t("connect_btn"), icon: "🧵", action: () => connectSelection() });
  }
  items.push({ label: t("select_neighbors"), icon: "⊕", action: () => G.selectNeighbors(ids) });
  items.push({ label: t("focus"), icon: "◉", action: () => G.focusOn(ids) });
  if (single) {
    items.push({ label: t("similar"), icon: "≈", action: () => showSimilar(single.id) });
    items.push({ label: t("link_to"), icon: "↗", action: () => A.startLinkMode(single.id) });
    items.push({ label: t("edit_value"), icon: "✎", action: () => A.editValue(single.id) });
  }
  if (!single && types.length === 1) items.push({ label: t("merge"), icon: "⧉", action: () => A.mergeEntities(ids) });
  items.push({ label: t("bookmark"), icon: "●", sub: A.BOOKMARKS.map((c) => ({
    label: c || "—", icon: c ? `<span style="color:${BOOKMARK_COLORS[c]}">●</span>` : "○", action: () => A.setBookmark(ids, c) })) });
  items.push({ label: t("copy_value"), icon: "⧉", action: () => A.copyValues(ids) });
  const url = single && safeUrl(single.value) && ["url", "account"].includes(single.type) ? single.value : null;
  if (url) items.push({ label: t("open_link"), icon: "↗", action: () => window.open(url, "_blank", "noopener,noreferrer") });
  items.push({ sep: true });
  items.push({ label: single ? t("delete") : t("delete_n", { n: ents.length }), icon: "✕", danger: true,
    action: () => A.deleteEntities(ids, { ask: ids.length > 1 }) });
  openMenu(ev, { head: single ? head(single) : `<span class="lbl">${esc(t("n_selected", { n: ents.length }))}</span>`, items });
}

async function showSimilar(id) {
  const r = await api(`/api/cases/${S.caseId}/similar`, { method: "POST", body: { ids: [id] } });
  if (!r.similar.length) {
    toast(t("none_found"));
    return;
  }
  const top = r.similar.slice(0, 6);
  const nodes = [id, ...top.map((x) => x.id), ...top.flatMap((x) => x.shared)];
  const pairs = top.flatMap((x) => x.shared.flatMap((m) => [[id, m], [x.id, m]]));
  G.highlight([...new Set(nodes)], pairs, [id, ...top.map((x) => x.id)]);
  toast(top.map((x) => `${short(S.entities.get(x.id)?.label || "", 22)} (${x.jaccard})`).join(" · "));
}

export function edgeMenu(ev, data) {
  const link = { src: data.source, dst: data.target, label: data.raw };
  const a = S.entities.get(link.src);
  const b = S.entities.get(link.dst);
  openMenu(ev, {
    head: `<span class="lbl">${esc(short(a?.label || "", 18))} → ${esc(data.label)} → ${esc(short(b?.label || "", 18))}</span>`,
    items: [
      { label: t("select_neighbors"), icon: "⊕", action: () => G.selectIds([link.src, link.dst]) },
      { label: t("edit_link"), icon: "✎", action: () => A.relabelLink(link) },
      { sep: true },
      { label: t("delete_link"), icon: "✕", danger: true, action: () => A.deleteLink(link) },
    ],
  });
}

export function canvasMenu(ev, pos) {
  const byCat = {};
  for (const [key, info] of Object.entries(S.types)) if (info.manual) (byCat[info.category] ||= []).push([key, info]);
  const sub = [];
  for (const [cat, items] of Object.entries(byCat)) {
    sub.push({ group: L(S.meta.entity_categories[cat]) });
    for (const [key, info] of items) {
      sub.push({ label: L(info.label), icon: iconSvg(key, info.color, 14), action: async () => {
        const r = await entityDialog({ type: key });
        if (r) await A.createEntity({ ...r, position: pos });
      } });
    }
  }
  openMenu(ev, { items: [
    { label: t("add_here"), icon: "+", sub },
    { label: t("select_all"), icon: "▣", action: () => G.cy.nodes(":visible").select() },
    { sep: true },
    { label: t("relayout"), icon: "⟲", action: () => G.runLayout(S.layoutName) },
    { label: t("fit"), icon: "⤢", action: () => G.fit() },
    { label: t("clear"), icon: "✧", action: () => G.clearHighlight() },
  ] });
}

export function exportMenu(ev) {
  const base = `/api/cases/${S.caseId}/export?format=`;
  const dl = (fmt) => () => {
    const a = document.createElement("a");
    a.href = base + fmt;
    a.download = "";
    document.body.append(a);
    a.click();
    a.remove();
  };
  openMenu(ev, { items: [
    { label: t("export_json"), icon: "{}", action: dl("json") },
    { label: t("export_graphml"), icon: "⋔", action: dl("graphml") },
    { label: t("export_csv"), icon: "▤", action: dl("csv") },
    { label: t("export_links"), icon: "⇄", action: dl("links-csv") },
    { sep: true },
    { label: t("export_png"), icon: "▧", action: () => G.exportPng(`daedalus_${(S.case?.name || "case").replace(/\W+/g, "_")}`) },
  ] });
}

export function caseMenu(ev, { rename, remove }) {
  openMenu(ev, { items: [
    { label: t("rename_case"), icon: "✎", action: rename },
    { sep: true },
    { label: t("delete_case"), icon: "✕", danger: true, action: remove },
  ] });
}
