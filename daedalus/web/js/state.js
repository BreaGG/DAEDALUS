// Shared client state and derived lookups.
import { store } from "./util.js";

export const S = {
  meta: null,
  types: {},
  transforms: {},
  machines: {},
  settings: null,
  cases: [],
  caseId: null,
  case: null,
  entities: new Map(),
  links: [],
  linkSet: new Set(),
  runs: [],
  selection: [],
  jobs: new Map(),
  running: new Map(), // `${eid}|${transform}` -> count
  tab: "graph",
  itab: "detail",
  limit: store.get("limit", 50),
  autoLayout: store.get("autoLayout", true),
  layoutName: store.get("layoutName", "organic"),
  loadImages: store.get("loadImages", false),
  hiddenTypes: new Set(),
  linkFrom: null,
  analysis: null,
  analysisStale: true,
  sizeBy: "none",
  colorBy: "type",
  showChoke: false,
  ariadne: { src: null, dst: null, paths: [], active: -1 },
};

export const BOOKMARK_COLORS = {
  red: "#e5534b", orange: "#f0883e", yellow: "#e3c33b", green: "#46b97a", blue: "#5aa9e6", purple: "#a371f7",
};

export const COMMUNITY_COLORS = [
  "#e6a23c", "#5aa9e6", "#e5534b", "#46b97a", "#a371f7", "#e879a6", "#4fc1b0", "#f2b25e", "#8b93f0", "#a3d468",
  "#ef6f6c", "#55cbdc", "#c98ae8", "#d9786a", "#7fd18b", "#b39a86",
];

export const typeInfo = (t) => S.types[t] || { label: { en: t, es: t }, color: "#9aa3ad", category: "artifact", manual: false };

export const linkKey = (l) => `${l.src}→${l.dst}|${l.label}`;

export function setLinks(links) {
  S.links = links;
  S.linkSet = new Set(links.map(linkKey));
}

export function pushLink(link) {
  const k = linkKey(link);
  if (S.linkSet.has(k)) return false;
  S.linkSet.add(k);
  S.links.push(link);
  return true;
}

export function dropLinksOf(ids) {
  const gone = new Set(ids);
  setLinks(S.links.filter((l) => !gone.has(l.src) && !gone.has(l.dst)));
}

export function neighbors(id) {
  const out = [];
  for (const l of S.links) {
    if (l.src === id) out.push({ id: l.dst, label: l.label, dir: "out" });
    else if (l.dst === id) out.push({ id: l.src, label: l.label, dir: "in" });
  }
  return out;
}

export function degree(id) {
  let n = 0;
  for (const l of S.links) if (l.src === id || l.dst === id) n++;
  return n;
}

export const selectedEntities = () => S.selection.map((id) => S.entities.get(id)).filter(Boolean);

export function transformsFor(types) {
  const set = new Set(types);
  return Object.values(S.transforms).filter((t) => t.inputs.some((i) => set.has(i)));
}

export function machinesFor(types) {
  const set = new Set(types);
  return Object.values(S.machines).filter((m) => m.generic || m.inputs.some((i) => set.has(i)));
}

export function lastRun(eid, transform) {
  for (let i = S.runs.length - 1; i >= 0; i--) {
    const r = S.runs[i];
    if (r.entity_id === eid && r.transform === transform) return r;
  }
  return null;
}

export const isRunning = (eid, transform) => (S.running.get(`${eid}|${transform}`) || 0) > 0;
export const entityBusy = (eid) => [...S.running.entries()].some(([k, v]) => v > 0 && k.startsWith(`${eid}|`));

// UI refresh callbacks, assigned by main.js (keeps modules free of import cycles)
export const hooks = {
  selection: () => {},
  views: () => {},
  palette: () => {},
  stale: () => {},
  reload: () => {},
  openSettings: async () => {},
};
