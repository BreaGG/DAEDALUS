// Right panel: entity detail and the transforms runner.
import { S, hooks, typeInfo, neighbors, selectedEntities, transformsFor, machinesFor, lastRun, isRunning, BOOKMARK_COLORS } from "./state.js";
import * as G from "./graph.js";
import { $, $$, esc, extLink, safeUrl, dateTime, short, store, toast } from "./util.js";
import { L, t, propLabel, linkLabel } from "./i18n.js";
import { iconSvg, uiIcon } from "./icons.js";
import { runTransforms, runMachine } from "./jobs.js";
import { promptDialog } from "./dialogs.js";
import * as A from "./actions.js";

let tfFilter = "";
const STATUS_ICON = { ok: "✓", empty: "∅", error: "✕", skipped: "»" };

export function setInspectorTab(tab) {
  S.itab = tab;
  $$(".insp-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.itab === tab));
  $("#detailPane").classList.toggle("hidden", tab !== "detail");
  $("#transformPane").classList.toggle("hidden", tab !== "transforms");
}

export function renderInspector() {
  const ents = selectedEntities();
  const detail = $("#detailPane");
  // a refresh (a save, a running transform…) must not swallow a note being typed
  const box = document.activeElement?.id === "entNotesBox" ? document.activeElement : null;
  const editing = box && { id: box.dataset.id, value: box.value, start: box.selectionStart, end: box.selectionEnd };
  if (!ents.length) detail.innerHTML = caseSummary();
  else if (ents.length === 1) detail.innerHTML = entityDetail(ents[0]);
  else detail.innerHTML = multiDetail(ents);
  const again = editing && $("#entNotesBox");
  if (again && again.dataset.id === editing.id) {
    again.value = editing.value;
    again.focus();
    again.setSelectionRange(editing.start, editing.end);
  }
  renderTransforms(ents);
}

// ------------------------------------------------------------------ detail
function caseSummary() {
  const counts = {};
  for (const e of S.entities.values()) counts[e.type] = (counts[e.type] || 0) + 1;
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = rows.length ? rows[0][1] : 1;
  const bars = rows.map(([type, n]) => {
    const info = typeInfo(type);
    return `<div class="type-row"><span class="ico" style="color:${info.color}">${iconSvg(type, info.color, 13)}</span>
      <span class="lbl">${esc(L(info.label))}</span><span class="bar"><i style="width:${Math.round((100 * n) / max)}%;background:${info.color}"></i></span>
      <span class="val">${n}</span></div>`;
  }).join("");
  return `${S.case ? `<div class="case-card"><div class="case-name">${esc(S.case.name)}</div>
      <div class="case-stats"><div><b>${S.entities.size}</b><span>${esc(t("an_entities"))}</span></div>
        <div><b>${S.links.length}</b><span>${esc(t("an_links"))}</span></div>
        <div><b>${rows.length}</b><span>${esc(t("types"))}</span></div></div></div>` : ""}
    <div class="placeholder">${esc(t("nothing_selected"))}</div>
    ${rows.length ? `<div class="block"><h4>${esc(t("by_type"))}</h4><div class="type-rows">${bars}</div></div>` : ""}
    <div class="block"><h4>${esc(t("shortcuts"))}</h4><div class="kb-list">${t("help_html")}</div></div>`;
}

function fmtValue(v) {
  if (Array.isArray(v)) {
    if (!v.length) return "";
    if (v.every((x) => typeof x !== "object")) return v.map((x) => `<span class="tag">${fmtScalar(x)}</span>`).join("");
    return `<code>${esc(JSON.stringify(v))}</code>`;
  }
  if (v && typeof v === "object") {
    return Object.entries(v).map(([k, x]) => `<div><span class="muted">${esc(k)}:</span> ${fmtScalar(x)}</div>`).join("");
  }
  return fmtScalar(v);
}

function fmtScalar(x) {
  if (x === true) return "✓";
  if (x === false) return "✗";
  const s = String(x ?? "");
  if (safeUrl(s)) return extLink(s, short(s, 60));
  if (s.length > 280) return `<details><summary>${esc(s.slice(0, 200))}…</summary>${esc(s)}</details>`;
  return esc(s);
}

function entityDetail(e) {
  const info = typeInfo(e.type);
  const props = Object.entries(e.props || {}).filter(([k, v]) => !k.startsWith("_") && v !== null && v !== "");
  const links = [...(e.props._links || [])];
  if (["url", "account"].includes(e.type) && safeUrl(e.value) && !links.some((l) => l[1] === e.value)) {
    links.unshift([t("open_link"), e.value]);
  }
  const nbs = neighbors(e.id);
  const runs = S.runs.filter((r) => r.entity_id === e.id).slice(-30).reverse();
  const img = safeUrl(e.props._image);
  const nTransforms = transformsFor([e.type]).filter((x) => x.default).length;
  const bms = A.BOOKMARKS.map((c) => `<span class="bm ${c ? "" : "none"} ${e.bookmark === c ? "on" : ""}" data-bm="${c}"
      style="${c ? `background:${BOOKMARK_COLORS[c]}` : ""}" title="${esc(c || "—")}"></span>`).join("");
  return `
    <div class="ent-head" style="color:${info.color}">
      <div class="big-ico">${iconSvg(e.type, info.color, 22)}</div>
      <div class="main">
        <div class="type">${esc(L(info.label))}${e.root ? `<span class="root-tag">${esc(t("root"))}</span>` : ""}</div>
        <div class="value">${esc(e.value)}</div>
        ${e.label !== e.value ? `<div class="muted small">${esc(e.label)}</div>` : ""}
      </div>
    </div>
    <div class="ent-actions">
      <button class="btn sm primary" data-act="runall" ${nTransforms ? "" : "disabled"}>${uiIcon("play", 12)}${esc(t("run_all_n", { n: nTransforms }))}</button>
      <button class="btn sm" data-act="tab-transforms">${esc(t("transforms"))}</button>
      <span class="grow"></span>
      <span class="btn-group">
      <button class="btn sm icon" data-act="edit" title="${esc(t("edit_value"))}">${uiIcon("edit")}</button>
      <button class="btn sm icon" data-act="copy" title="${esc(t("copy_value"))}">${uiIcon("copy")}</button>
      <button class="btn sm icon" data-act="link" title="${esc(t("link_to"))}">${uiIcon("link")}</button>
      <button class="btn sm icon danger" data-act="delete" title="${esc(t("delete"))}">${uiIcon("trash")}</button>
      </span>
    </div>
    <div class="bm-row"><span class="field-k">${esc(t("bookmark"))}</span>${bms}</div>
    ${img ? `<div class="img-box">${S.loadImages ? `<img src="${esc(img)}" referrerpolicy="no-referrer" alt="">`
      : `<button class="btn sm" data-act="load-img" data-src="${esc(img)}">${esc(t("load_image"))}</button>`}</div>` : ""}
    <div class="block"><h4>${esc(t("properties"))} <button class="btn xs ghost" data-act="add-prop">${uiIcon("plus", 11)}${esc(t("add_property"))}</button></h4>
      ${props.length ? `<table class="props">${props.map(([k, v]) => `<tr><td class="k">${esc(propLabel(k))}</td>
        <td class="v">${fmtValue(v)}<span class="x" data-del-prop="${esc(k)}" title="${esc(t("delete"))}">${uiIcon("x", 11)}</span></td></tr>`).join("")}</table>`
        : `<div class="muted small">—</div>`}
    </div>
    ${links.length ? `<div class="block"><h4>${esc(t("links_ext"))}</h4><div class="link-list">
      ${links.map(([label, url]) => `<div>${uiIcon("link", 11)}${extLink(url, label)}</div>`).join("")}</div></div>` : ""}
    ${(e.props._unverified || []).length ? `<div class="block"><h4>${esc(t("unverified"))} (${e.props._unverified.length})</h4>
      <div class="muted small gap-b">${esc(t("unverified_help"))}</div>
      <div class="link-list">${e.props._unverified.map(([name, url]) => `<div><span class="q">?</span>${extLink(url, name)}</div>`).join("")}</div></div>` : ""}
    ${(e.props._dates || []).length ? `<div class="block"><h4>${esc(t("dates"))}</h4>
      ${e.props._dates.map(([label, d]) => `<div class="small"><span class="mono muted">${esc(d)}</span> · ${esc(label)}</div>`).join("")}</div>` : ""}
    <div class="block"><h4>${esc(t("connections"))} <span class="count">${nbs.length}</span></h4>
      ${nbs.slice(0, 80).map((nb) => {
        const other = S.entities.get(nb.id);
        if (!other) return "";
        return `<div class="nb-row" data-goto="${esc(nb.id)}">
          <span style="color:${typeInfo(other.type).color}">${iconSvg(other.type, typeInfo(other.type).color, 14)}</span>
          <span class="rel">${nb.dir === "out" ? "→" : "←"} ${esc(linkLabel(nb.label))}</span>
          <span class="lbl" title="${esc(other.value)}">${esc(other.label)}</span></div>`;
      }).join("") || `<div class="muted small">—</div>`}
      ${nbs.length > 80 ? `<div class="muted small">+${nbs.length - 80}</div>` : ""}
    </div>
    <div class="block"><h4>${esc(t("notes"))}</h4><textarea class="notes-box" id="entNotesBox" data-id="${esc(e.id)}" rows="3">${esc(e.notes || "")}</textarea></div>
    ${(e.props._sources || []).length ? `<div class="block"><h4>${esc(t("sources"))}</h4>
      <div class="chips">${e.props._sources.map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div></div>` : ""}
    ${runs.length ? `<div class="block"><h4>${esc(t("history"))}</h4>${runs.map((r) => `
      <div class="run-row"><span class="st-${esc(r.status)}">${STATUS_ICON[r.status] || "·"}</span>
        <span>${esc(L(S.transforms[r.transform]?.title) || r.transform)}</span><span class="dim">${esc(dateTime(r.finished).split(" ")[1] || "")}</span>
        <span class="m">${esc(r.message || "")}</span></div>`).join("")}</div>` : ""}
  `;
}

function multiDetail(ents) {
  const counts = {};
  for (const e of ents) counts[e.type] = (counts[e.type] || 0) + 1;
  const types = Object.keys(counts);
  const sameType = types.length === 1;
  return `
    <div class="block"><h4>${esc(t("n_selected", { n: ents.length }))}</h4>
      <div class="chips">${Object.entries(counts).map(([type, n]) =>
        `<span class="chip"><span class="dot" style="background:${typeInfo(type).color}"></span>${esc(L(typeInfo(type).label))} · ${n}</span>`).join("")}</div></div>
    <div class="ent-actions">
      <button class="btn sm primary" data-act="runall">${uiIcon("play", 12)}${esc(t("run_all"))}</button>
      <button class="btn sm" data-act="tab-transforms">${esc(t("transforms"))}</button>
      <button class="btn sm" data-act="connect">${uiIcon("thread")}${esc(t("connect_btn"))}</button>
      ${sameType ? `<button class="btn sm" data-act="merge">${esc(t("merge"))}</button>` : ""}
      <button class="btn sm" data-act="neighbors">${esc(t("select_neighbors"))}</button>
      <button class="btn sm danger" data-act="delete">${esc(t("delete_n", { n: ents.length }))}</button>
    </div>
    <div class="block">${ents.slice(0, 60).map((e) => `<div class="nb-row" data-goto="${esc(e.id)}">
      <span style="color:${typeInfo(e.type).color}">${iconSvg(e.type, typeInfo(e.type).color, 14)}</span>
      <span class="lbl">${esc(e.label)}</span></div>`).join("")}</div>`;
}

// -------------------------------------------------------------- transforms
export function renderTransforms(ents = selectedEntities()) {
  const pane = $("#transformPane");
  const hadFocus = document.activeElement?.id === "tfFilter";
  if (!ents.length) {
    pane.innerHTML = `<div class="placeholder">${esc(t("nothing_selected"))}</div>`;
    return;
  }
  const types = [...new Set(ents.map((e) => e.type))];
  const q = tfFilter.toLowerCase();
  const list = transformsFor(types).filter((x) => !q || `${L(x.title)} ${L(x.description)} ${x.name}`.toLowerCase().includes(q));
  const single = ents.length === 1 ? ents[0] : null;
  const byCat = {};
  for (const tr of list) (byCat[tr.category] ||= []).push(tr);
  const limits = [12, 50, 255, 1000];
  let html = `<div class="tf-filter"><input id="tfFilter" type="search" placeholder="${esc(t("filter_transforms"))}" value="${esc(tfFilter)}">
      <select id="tfLimit" title="${esc(t("result_limit"))}">${limits.map((n) => `<option ${n === S.limit ? "selected" : ""}>${n}</option>`).join("")}</select></div>
    <button class="btn sm primary wide" data-act="runall">${uiIcon("play", 12)}${esc(t("run_all_n", { n: list.filter((x) => x.default).length }))}</button>`;
  if (!list.length) html += `<div class="muted small">${esc(t("no_transforms"))}</div>`;
  for (const [cat, items] of Object.entries(byCat)) {
    html += `<div class="tf-cat"><div class="cat-name">${esc(L(S.meta.transform_categories[cat]) || cat)}</div>`;
    for (const tr of items) {
      const locked = !tr.ready;
      const run = single ? lastRun(single.id, tr.name) : null;
      const running = single ? isRunning(single.id, tr.name) : false;
      const last = run ? `<span class="st-${esc(run.status)}" title="${esc(run.message || "")}">${STATUS_ICON[run.status] || ""}${run.found ? ` ${run.found}` : ""}</span>` : "";
      html += `<div class="tf-item ${locked ? "locked" : ""} ${running ? "running" : ""}" data-t="${esc(tr.name)}">
        <div class="tt">${esc(L(tr.title))}${locked ? `<span class="key">${uiIcon("key", 11)}${esc(tr.keys.join(", "))}</span>` : ""}</div>
        <div class="last">${last}</div>
        <div class="ds">${esc(L(tr.description))}${tr.sources.length ? ` · <i>${esc(tr.sources.join(", "))}</i>` : ""}</div></div>`;
    }
    html += "</div>";
  }
  const machines = machinesFor(types);
  if (machines.length) {
    html += `<div class="tf-cat"><div class="cat-name">${esc(t("machines"))}</div>`;
    for (const m of machines) {
      html += `<div class="tf-item" data-m="${esc(m.name)}" title="${esc(L(m.description))}">
        <div class="tt">${uiIcon("cpu", 12)}${esc(L(m.title))}</div><div class="last">${m.generic ? `<select data-depth="${esc(m.name)}" title="${esc(t("machine_depth"))}">
          ${[1, 2, 3].map((d) => `<option ${d === 2 ? "selected" : ""}>${d}</option>`).join("")}</select>` : ""}</div>
        <div class="ds">${esc(L(m.description))}</div></div>`;
    }
    html += "</div>";
  }
  pane.innerHTML = html;
  if (hadFocus) {
    const f = $("#tfFilter");
    f.focus();
    f.setSelectionRange(f.value.length, f.value.length);
  }
}

// ------------------------------------------------------------------ events
export function initInspector() {
  $$(".insp-tabs .tab").forEach((b) => b.addEventListener("click", () => setInspectorTab(b.dataset.itab)));
  let pendingNote = null;
  let noteTimer = null;
  const saveNote = () => {
    clearTimeout(noteTimer);
    if (!pendingNote) return;
    const { id, notes } = pendingNote;
    pendingNote = null;
    if (S.entities.has(id)) A.updateEntity(id, { notes }).catch(() => {});
  };

  for (const pane of [$("#detailPane"), $("#transformPane")]) {
    pane.addEventListener("click", async (ev) => {
      const el = ev.target.closest("[data-act],[data-goto],[data-bm],[data-del-prop],[data-t],[data-m]");
      if (!el || ev.target.closest("select")) return;
      const ids = [...S.selection];
      try {
        if (el.dataset.goto) {
          G.selectIds([el.dataset.goto], { center: true });
        } else if (el.dataset.bm !== undefined) {
          await A.setBookmark(ids, el.dataset.bm);
        } else if (el.dataset.delProp) {
          await A.updateEntity(ids[0], { replace: { [el.dataset.delProp]: null } });
        } else if (el.dataset.t) {
          const tr = S.transforms[el.dataset.t];
          if (!tr.ready) {
            await hooks.openSettings("keys");
            return;
          }
          await runTransforms(ids, [tr.name]);
        } else if (el.dataset.m) {
          const depthSel = el.querySelector("select[data-depth]");
          await runMachine(ids, el.dataset.m, depthSel ? Number(depthSel.value) : 2);
        } else {
          await act(el.dataset.act, ids, el);
        }
      } catch (e) {
        console.error(e);
        toast(e.message, "error");
      }
    });
  }
  $("#transformPane").addEventListener("input", (ev) => {
    if (ev.target.id === "tfFilter") {
      tfFilter = ev.target.value;
      renderTransforms();
    }
  });
  $("#transformPane").addEventListener("change", (ev) => {
    if (ev.target.id === "tfLimit") {
      S.limit = Number(ev.target.value);
      store.set("limit", S.limit);
    }
  });
  $("#detailPane").addEventListener("input", (ev) => {
    if (ev.target.id !== "entNotesBox") return;
    pendingNote = { id: ev.target.dataset.id, notes: ev.target.value };
    clearTimeout(noteTimer);
    noteTimer = setTimeout(saveNote, 700);
  });
  $("#detailPane").addEventListener("focusout", (ev) => { if (ev.target.id === "entNotesBox") saveNote(); });
}

async function act(name, ids, el) {
  switch (name) {
    case "runall": return runTransforms(ids, null);
    case "tab-transforms": return setInspectorTab("transforms");
    case "edit": return A.editValue(ids[0]);
    case "copy": return A.copyValues(ids);
    case "link": return A.startLinkMode(ids[0]);
    case "delete": return A.deleteEntities(ids, { ask: ids.length > 1 });
    case "merge": return A.mergeEntities(ids);
    case "neighbors": return G.selectNeighbors(ids);
    case "connect": return (await import("./ariadne.js")).connectSelection();
    case "load-img": {
      const src = safeUrl(el.dataset.src);
      if (src) el.parentElement.innerHTML = `<img src="${esc(src)}" referrerpolicy="no-referrer" alt="">`;
      return null;
    }
    case "add-prop": {
      const key = await promptDialog({ title: t("prop_name"), ok: "OK" });
      if (!key) return null;
      const value = await promptDialog({ title: `${t("prop_value")} · ${key}`, ok: t("save") });
      if (value === null) return null;
      return A.updateEntity(ids[0], { replace: { [key.trim().replace(/^_+/, "")]: value } });
    }
    default: return null;
  }
}
