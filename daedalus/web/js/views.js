// Secondary views: entity table, map, timeline and case notes.
import { S, typeInfo, degree, BOOKMARK_COLORS } from "./state.js";
import * as G from "./graph.js";
import { $, esc, debounce, dateTime, short, api } from "./util.js";
import { L as label, t } from "./i18n.js";
import { iconSvg } from "./icons.js";

const Leaflet = window.L;
let sort = { key: "created", dir: -1 };
const marked = new Set();
let map = null;
let mapLayer = null;

export function renderView() {
  if (S.tab === "table") renderTable();
  else if (S.tab === "map") renderMap();
  else if (S.tab === "timeline") renderTimeline();
  else if (S.tab === "notes") $("#notesArea").value = S.case?.notes || "";
}

// ------------------------------------------------------------------ table
export function fillTypeFilter() {
  const sel = $("#tableType");
  const cur = sel.value;
  const present = [...new Set([...S.entities.values()].map((e) => e.type))];
  sel.innerHTML = `<option value="">${esc(t("all_types"))}</option>` + present.map((ty) =>
    `<option value="${ty}" ${ty === cur ? "selected" : ""}>${esc(label(typeInfo(ty).label))}</option>`).join("");
}

export function renderTable() {
  fillTypeFilter();
  const q = $("#tableFilter").value.trim().toLowerCase();
  const ty = $("#tableType").value;
  let rows = [...S.entities.values()].filter((e) => (!ty || e.type === ty)
    && (!q || `${e.label} ${e.value} ${JSON.stringify(e.props)} ${e.notes}`.toLowerCase().includes(q)));
  const keyFn = {
    type: (e) => e.type, value: (e) => e.label.toLowerCase(), links: (e) => degree(e.id),
    sources: (e) => (e.props._sources || []).join(","), created: (e) => e.created,
  }[sort.key];
  rows.sort((a, b) => (keyFn(a) > keyFn(b) ? 1 : keyFn(a) < keyFn(b) ? -1 : 0) * sort.dir);
  const total = rows.length;
  rows = rows.slice(0, 3000);
  const sel = new Set(S.selection);
  const arrow = (k) => (sort.key === k ? (sort.dir > 0 ? " ▲" : " ▼") : "");
  $("#entityTable").innerHTML = `<thead><tr><th style="width:28px"><input type="checkbox" id="markAll"></th>
      <th data-sort="type">${esc(t("col_type"))}${arrow("type")}</th><th data-sort="value">${esc(t("col_value"))}${arrow("value")}</th>
      <th data-sort="links">${esc(t("col_links"))}${arrow("links")}</th><th data-sort="sources">${esc(t("col_sources"))}${arrow("sources")}</th>
      <th data-sort="created">${esc(t("col_added"))}${arrow("created")}</th></tr></thead><tbody>
    ${rows.map((e) => {
      const info = typeInfo(e.type);
      return `<tr data-id="${esc(e.id)}" class="${sel.has(e.id) ? "sel" : ""}">
        <td><input type="checkbox" data-mark="${esc(e.id)}" ${marked.has(e.id) ? "checked" : ""}></td>
        <td><span class="tcell" style="color:${info.color}">${iconSvg(e.type, info.color, 14)}<span style="color:var(--text)">${esc(label(info.label))}</span></span></td>
        <td title="${esc(e.value)}">${e.bookmark ? `<span class="bm-dot" style="background:${BOOKMARK_COLORS[e.bookmark]}"></span>` : ""}${esc(short(e.label, 80))}${e.root ? ` <span class="root-tag">${esc(t("root"))}</span>` : ""}</td>
        <td class="mono">${degree(e.id)}</td>
        <td class="muted">${esc((e.props._sources || []).join(", "))}</td>
        <td class="muted mono">${esc(dateTime(e.created))}</td></tr>`;
    }).join("")}
    ${total > rows.length ? `<tr><td colspan="6" class="muted">+${total - rows.length}</td></tr>` : ""}</tbody>`;
  $("#tableDelete").disabled = !marked.size;
}

export function initTable(onDelete) {
  $("#tableFilter").addEventListener("input", debounce(renderTable, 200));
  $("#tableType").addEventListener("change", renderTable);
  $("#entityTable").addEventListener("click", (ev) => {
    const th = ev.target.closest("th[data-sort]");
    if (th) {
      sort = { key: th.dataset.sort, dir: sort.key === th.dataset.sort ? -sort.dir : 1 };
      renderTable();
      return;
    }
    if (ev.target.id === "markAll") {
      document.querySelectorAll("#entityTable [data-mark]").forEach((cb) => {
        cb.checked = ev.target.checked;
        if (cb.checked) marked.add(cb.dataset.mark);
        else marked.delete(cb.dataset.mark);
      });
      $("#tableDelete").disabled = !marked.size;
      return;
    }
    const cb = ev.target.closest("[data-mark]");
    if (cb) {
      if (cb.checked) marked.add(cb.dataset.mark);
      else marked.delete(cb.dataset.mark);
      $("#tableDelete").disabled = !marked.size;
      return;
    }
    const tr = ev.target.closest("tr[data-id]");
    if (tr) {
      G.selectIds([tr.dataset.id]);
      document.querySelectorAll("#entityTable tr.sel").forEach((r) => r.classList.remove("sel"));
      tr.classList.add("sel");
    }
  });
  $("#tableDelete").addEventListener("click", async () => {
    await onDelete([...marked]);
    marked.clear();
    renderTable();
  });
}

export const clearMarks = () => marked.clear();

// -------------------------------------------------------------------- map
function located() {
  return [...S.entities.values()].filter((e) => Number.isFinite(Number(e.props._lat)) && Number.isFinite(Number(e.props._lon))
    && e.props._lat !== null && e.props._lon !== null && e.props._lat !== "" && e.props._lon !== "");
}

export function renderMap() {
  if (!Leaflet) return;
  if (!map) {
    map = Leaflet.map("map", { worldCopyJump: true, zoomControl: true }).setView([20, 0], 2);
    Leaflet.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19, subdomains: "abcd",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    }).addTo(map);
    mapLayer = Leaflet.layerGroup().addTo(map);
  }
  setTimeout(() => map.invalidateSize(), 50);
  mapLayer.clearLayers();
  const pts = located();
  $("#mapEmpty").classList.toggle("hidden", pts.length > 0);
  const bounds = [];
  for (const e of pts) {
    const lat = Number(e.props._lat);
    const lon = Number(e.props._lon);
    const info = typeInfo(e.type);
    const nbs = S.links.filter((l) => l.src === e.id || l.dst === e.id).slice(0, 10)
      .map((l) => S.entities.get(l.src === e.id ? l.dst : l.src)).filter(Boolean);
    const m = Leaflet.circleMarker([lat, lon], { radius: e.type === "location" ? 8 : 6, color: info.color, weight: 2,
      fillColor: info.color, fillOpacity: 0.35 });
    m.bindPopup(`<b>${esc(e.label)}</b><br><span style="color:${info.color}">${esc(label(info.label))}</span>
      ${e.props.precision ? `<br><i>${esc(e.props.precision)}</i>` : ""}
      ${nbs.length ? `<hr style="border-color:#333">${nbs.map((n) => `<div>${esc(short(n.label, 40))}</div>`).join("")}` : ""}
      <br><a href="#" data-goto="${esc(e.id)}">→ ${esc(t("tab_graph"))}</a>`);
    m.on("popupopen", (ev) => {
      ev.popup.getElement()?.querySelector("[data-goto]")?.addEventListener("click", (x) => {
        x.preventDefault();
        document.querySelector('.tab[data-tab="graph"]').click();
        G.selectIds([e.id], { center: true });
      });
    });
    m.addTo(mapLayer);
    bounds.push([lat, lon]);
  }
  if (bounds.length === 1) map.setView(bounds[0], 10);
  else if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
}

// --------------------------------------------------------------- timeline
export function renderTimeline() {
  const items = [];
  for (const e of S.entities.values()) {
    for (const d of e.props._dates || []) {
      if (!Array.isArray(d) || !d[1]) continue;
      const date = String(d[1]).slice(0, 10);
      if (!/^\d{4}/.test(date)) continue;
      items.push({ date, what: d[0], ent: e });
    }
  }
  items.sort((a, b) => a.date.localeCompare(b.date));
  const box = $("#timeline");
  if (!items.length) {
    box.innerHTML = `<div class="view-empty">${esc(t("timeline_empty"))}</div>`;
    return;
  }
  let html = "";
  let year = null;
  for (const it of items) {
    const y = it.date.slice(0, 4);
    if (y !== year) {
      year = y;
      html += `<div class="tl-year">${esc(y)}</div>`;
    }
    const info = typeInfo(it.ent.type);
    html += `<div class="tl-item" style="color:${info.color}"><div class="d">${esc(it.date)}</div><div class="pin"></div>
      <div class="what" data-goto="${esc(it.ent.id)}" style="color:var(--text)"><b>${esc(it.what)}</b>
        <div class="small muted"><span style="color:${info.color}">${iconSvg(it.ent.type, info.color, 12)}</span> ${esc(short(it.ent.label, 70))}</div></div></div>`;
  }
  box.innerHTML = html;
}

export function initTimeline() {
  $("#timeline").addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-goto]");
    if (!el) return;
    document.querySelector('.tab[data-tab="graph"]').click();
    G.selectIds([el.dataset.goto], { center: true });
  });
}

// ------------------------------------------------------------------ notes
export function initNotes() {
  const save = debounce(async (caseId, notes) => {
    try {
      S.case = await api(`/api/cases/${caseId}`, { method: "PATCH", body: { notes } });
    } catch { /* retried on next keystroke */ }
  }, 700);
  $("#notesArea").addEventListener("input", (ev) => {
    if (S.case) S.case.notes = ev.target.value;
    if (S.caseId) save(S.caseId, ev.target.value);
  });
}
