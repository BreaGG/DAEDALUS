// Cytoscape canvas: styling, node placement, layouts, highlighting and persistence.
import { S, typeInfo, BOOKMARK_COLORS, COMMUNITY_COLORS, linkKey } from "./state.js";
import { iconUri } from "./icons.js";
import { api, debounce, download, short } from "./util.js";
import { L, linkLabel } from "./i18n.js";

/* global cytoscape, cytoscapeFcose, cytoscapeDagre */
if (typeof cytoscapeFcose !== "undefined") cytoscape.use(cytoscapeFcose);
if (typeof cytoscapeDagre !== "undefined") cytoscape.use(cytoscapeDagre);
const HAS_FCOSE = typeof cytoscapeFcose !== "undefined";
const HAS_DAGRE = typeof cytoscapeDagre !== "undefined";

export let cy = null;
let H = {};
let pathActive = false;
let edgeLabels = false;
const spawned = new Map(); // parent id -> children placed around it

const STYLE = [
  { selector: "node", style: {
    "background-color": "#141a21", "background-image": "data(icon)", "background-fit": "none",
    "background-width": "54%", "background-height": "54%", "background-clip": "none",
    "border-width": 2, "border-color": "data(color)", width: "data(size)", height: "data(size)", shape: "ellipse",
    label: "data(short)", color: "#d8d2c4", "font-size": 10, "font-family": "system-ui, -apple-system, Segoe UI, sans-serif",
    "text-valign": "bottom", "text-halign": "center", "text-margin-y": 5, "text-outline-color": "#0a0d11",
    "text-outline-width": 2.5, "min-zoomed-font-size": 7, "text-wrap": "ellipsis", "text-max-width": 160,
    "underlay-shape": "ellipse",
  } },
  { selector: 'node[ccolor != ""]', style: { "border-color": "data(ccolor)", "border-width": 3 } },
  { selector: "node[?root]", style: { "border-width": 3, "border-color": "#d6a84f", "font-weight": "bold", color: "#f0cd7c",
    "underlay-color": "#d6a84f", "underlay-opacity": 0.13, "underlay-padding": 9, "underlay-shape": "ellipse" } },
  { selector: 'node[bmcolor != ""]', style: { "outline-width": 3, "outline-color": "data(bmcolor)", "outline-offset": 3 } },
  { selector: "node.choke", style: { "border-style": "double", "border-width": 6, "border-color": "#e5534b" } },
  { selector: "node.scanning", style: { "border-style": "dashed", "border-color": "#f0cd7c", "border-width": 3 } },
  { selector: "node.hit", style: { "underlay-color": "#5aa9e6", "underlay-opacity": 0.4, "underlay-padding": 11, "underlay-shape": "ellipse" } },
  { selector: "node:selected", style: { "border-width": 3.5, "border-color": "#ffffff", "underlay-color": "#f0cd7c",
    "underlay-opacity": 0.3, "underlay-padding": 8, "underlay-shape": "ellipse" } },
  { selector: "node.path-node", style: { "border-color": "#e5534b", "border-width": 3.5, "underlay-color": "#e5534b",
    "underlay-opacity": 0.25, "underlay-padding": 9, color: "#ffd9d6", "z-index": 20 } },
  { selector: "node.path-end", style: { "border-color": "#f0cd7c", "underlay-color": "#f0cd7c", "underlay-opacity": 0.35 } },
  { selector: "edge", style: {
    width: 1.3, "line-color": "#36404b", "target-arrow-color": "#36404b", "target-arrow-shape": "triangle", "arrow-scale": 0.75,
    "curve-style": "bezier", label: "data(label)", "font-size": 8.5, color: "#aab2bb", "text-rotation": "autorotate",
    "text-opacity": 0, "text-background-color": "#0a0d11", "text-background-opacity": 0.85, "text-background-padding": 2,
    "text-background-shape": "roundrectangle", "min-zoomed-font-size": 6,
  } },
  { selector: "edge.lbl", style: { "text-opacity": 1 } },
  { selector: 'edge[transform = "manual"]', style: { "line-style": "dashed", "line-color": "#7a6232", "target-arrow-color": "#7a6232" } },
  { selector: "edge.bridge", style: { "line-color": "#b8433d", "target-arrow-color": "#b8433d", "line-style": "dashed", width: 2.2 } },
  { selector: "edge.hl", style: { "line-color": "#d6a84f", "target-arrow-color": "#d6a84f", width: 2, "text-opacity": 1, "z-index": 10 } },
  { selector: "edge.path-edge", style: { "line-color": "#e5534b", "target-arrow-color": "#e5534b", width: 3.2, "text-opacity": 1,
    color: "#ffd9d6", "z-index": 20 } },
  { selector: ".faded", style: { opacity: 0.1 } },
  { selector: ".type-hidden", style: { display: "none" } },
];

export function initGraph(container, handlers) {
  H = handlers;
  cy = cytoscape({
    container, style: STYLE, wheelSensitivity: 0.25, minZoom: 0.05, maxZoom: 4, boxSelectionEnabled: true,
    selectionType: "single",
  });
  let selTimer = null;
  cy.on("select unselect", "node", () => {
    if (selTimer) return;
    selTimer = requestAnimationFrame(() => {
      selTimer = null;
      S.selection = cy.nodes(":selected").map((n) => n.id());
      H.onSelection?.();
    });
  });
  cy.on("tap", "node", (e) => {
    if (S.linkFrom) {
      H.onLinkTarget?.(e.target.id());
    }
  });
  cy.on("dbltap", "node", (e) => H.onNodeDbl?.(e.target.id()));
  cy.on("cxttap", "node", (e) => {
    const n = e.target;
    if (!n.selected()) {
      cy.nodes().unselect();
      n.select();
    }
    H.onNodeMenu?.(e.originalEvent, cy.nodes(":selected").map((x) => x.id()));
  });
  cy.on("cxttap", "edge", (e) => H.onEdgeMenu?.(e.originalEvent, e.target.data()));
  cy.on("cxttap", (e) => { if (e.target === cy) H.onCanvasMenu?.(e.originalEvent, e.position); });
  cy.on("tap", (e) => { if (e.target === cy) H.onCanvasTap?.(); });
  cy.on("mouseover", "node", (e) => {
    if (pathActive) return;
    const hood = e.target.closedNeighborhood();
    cy.batch(() => {
      cy.elements().not(hood).addClass("faded");
      hood.edges().addClass("hl");
    });
  });
  cy.on("mouseout", "node", () => {
    if (pathActive) return;
    cy.batch(() => { cy.elements().removeClass("faded"); cy.edges().removeClass("hl"); });
  });
  cy.on("dragfree", "node", savePositionsSoon);
  new ResizeObserver(() => cy.resize()).observe(container);
  return cy;
}

// ------------------------------------------------------------------- nodes
function baseSize(ent) {
  return ent.root ? 46 : 34;
}

export function nodeData(ent) {
  const t = typeInfo(ent.type);
  const node = cy.getElementById(ent.id);
  const prev = node.nonempty() ? node.data() : null;
  return {
    id: ent.id,
    type: ent.type,
    label: ent.label,
    value: ent.value,
    short: short(ent.label, 30),
    color: t.color,
    icon: iconUri(ent.type, t.color),
    size: prev?.metricSize || baseSize(ent),
    metricSize: prev?.metricSize || 0,
    root: !!ent.root,
    bmcolor: BOOKMARK_COLORS[ent.bookmark] || "",
    ccolor: prev?.ccolor || "",
  };
}

function viewportCenter() {
  const ext = cy.extent();
  return { x: (ext.x1 + ext.x2) / 2, y: (ext.y1 + ext.y2) / 2 };
}

function isFree(p, minDist = 80) {
  const nodes = cy.nodes();
  if (nodes.length > 1500) return true; // too big to check cheaply; the spiral alone spreads them
  return nodes.every((n) => {
    const q = n.position();
    return Math.hypot(q.x - p.x, q.y - p.y) > minDist;
  });
}

// next free slot on a sunflower spiral around `center`
function spiral(center, start, base, step) {
  for (let i = start; i < start + 500; i++) {
    const angle = i * 2.399963;
    const r = base + step * Math.sqrt(i);
    const p = { x: center.x + Math.cos(angle) * r, y: center.y + Math.sin(angle) * r };
    if (isFree(p, 62)) return { p, i };
  }
  return { p: { x: center.x + (Math.random() - 0.5) * 300, y: center.y + (Math.random() - 0.5) * 300 }, i: start + 1 };
}

function placeNear(parentId) {
  const parent = parentId ? cy.getElementById(parentId) : null;
  if (parent && parent.nonempty()) {
    const { p, i } = spiral(parent.position(), (spawned.get(parentId) || 0) + 1, 70, 26);
    spawned.set(parentId, i);
    return p;
  }
  if (!cy.nodes().length) return { x: 0, y: 0 };
  return spiral(viewportCenter(), 0, 0, 110).p;
}

export function upsertNode(ent, parentId = null, position = null) {
  const node = cy.getElementById(ent.id);
  if (node.nonempty()) {
    node.data(nodeData(ent));
    return false;
  }
  const n = cy.add({ group: "nodes", data: nodeData(ent), position: position || placeNear(parentId) });
  if (S.hiddenTypes.has(ent.type)) n.addClass("type-hidden");
  return true;
}

export function removeNodes(ids) {
  cy.batch(() => ids.forEach((id) => cy.getElementById(id).remove()));
}

export function addEdge(link) {
  const id = linkKey(link);
  if (cy.getElementById(id).nonempty()) return;
  if (cy.getElementById(link.src).empty() || cy.getElementById(link.dst).empty()) return;
  const e = cy.add({ group: "edges", data: { id, source: link.src, target: link.dst, label: linkLabel(link.label),
    raw: link.label, transform: link.transform || "" } });
  if (edgeLabels) e.addClass("lbl");
}

export function removeEdge(link) {
  cy.getElementById(linkKey(link)).remove();
}

export function relabelEdges() {
  cy.edges().forEach((e) => e.data("label", linkLabel(e.data("raw"))));
}

export function setEdgeLabels(on) {
  edgeLabels = on;
  cy.edges().toggleClass("lbl", on);
}

export function setScanning(id, on) {
  cy.getElementById(id).toggleClass("scanning", on);
}

export function applyTypeVisibility() {
  cy.batch(() => cy.nodes().forEach((n) => n.toggleClass("type-hidden", S.hiddenTypes.has(n.data("type")))));
}

// ----------------------------------------------------------------- loading
export function loadGraph(entities, links, layout) {
  spawned.clear();
  pathActive = false;
  const positions = (layout && layout.positions) || {};
  let missing = 0;
  cy.batch(() => {
    cy.elements().remove();
    for (const ent of entities) {
      const p = positions[ent.id];
      if (!p) missing++;
      cy.add({ group: "nodes", data: nodeData(ent), position: p ? { x: p[0], y: p[1] } : { x: 0, y: 0 } });
    }
    for (const l of links) addEdge(l);
  });
  if (missing && missing === entities.length) {
    runLayout(S.layoutName, { randomize: true, animate: false });
  } else if (missing) {
    cy.nodes().forEach((n) => {
      if (positions[n.id()]) return;
      const anchor = n.neighborhood("node").filter((m) => positions[m.id()]).first();
      n.position(placeNear(anchor.nonempty() ? anchor.id() : null));
    });
    cy.fit(undefined, 40);
  } else if (entities.length) {
    cy.fit(undefined, 40);
  }
  applyTypeVisibility();
}

export const savePositionsSoon = debounce(() => {
  if (!S.caseId || !cy) return;
  const positions = {};
  cy.nodes().forEach((n) => {
    const p = n.position();
    positions[n.id()] = [Math.round(p.x), Math.round(p.y)];
  });
  const caseId = S.caseId;
  api(`/api/cases/${caseId}`, { method: "PATCH", body: { layout: { positions, layoutName: S.layoutName } } }).catch(() => {});
}, 1200);

// ----------------------------------------------------------------- layouts
export function runLayout(name = S.layoutName, { fit = true, randomize = false, animate } = {}) {
  const eles = cy.elements().not(".type-hidden");
  const n = eles.nodes().length;
  if (!n) return;
  animate = animate ?? n < 400;
  let opts;
  switch (name) {
    case "hierarchical":
      opts = HAS_DAGRE ? { name: "dagre", rankDir: "TB", nodeSep: 36, rankSep: 90, edgeSep: 12 }
        : { name: "breadthfirst", directed: true, spacingFactor: 1.2 };
      break;
    case "radial": {
      const roots = eles.nodes("[?root]");
      opts = { name: "breadthfirst", circle: true, spacingFactor: 1.05, directed: false, roots: roots.nonempty() ? roots : undefined };
      break;
    }
    case "circular":
      opts = { name: "circle", avoidOverlap: true, spacingFactor: 1.05 };
      break;
    case "concentric":
      opts = { name: "concentric", concentric: (x) => x.degree(), levelWidth: () => 2, minNodeSpacing: 34, avoidOverlap: true };
      break;
    case "block":
      opts = { name: "grid", avoidOverlap: true, avoidOverlapPadding: 26, condense: true,
        sort: (a, b) => a.data("type").localeCompare(b.data("type")) || a.data("label").localeCompare(b.data("label")) };
      break;
    default:
      opts = HAS_FCOSE
        ? { name: "fcose", quality: n > 900 ? "draft" : "default", randomize, nodeRepulsion: 7500, idealEdgeLength: 92,
          edgeElasticity: 0.4, nodeSeparation: 85, gravity: 0.3, numIter: 2500, packComponents: true, tile: true }
        : { name: "cose", randomize, nodeRepulsion: 9000, idealEdgeLength: 90 };
  }
  const layout = eles.layout({ ...opts, animate, animationDuration: 450, fit, padding: 40 });
  layout.one("layoutstop", savePositionsSoon);
  layout.run();
}

export const fit = () => cy.animate({ fit: { eles: cy.elements().not(".type-hidden"), padding: 40 } }, { duration: 300 });
export const zoomBy = (f) => cy.zoom({ level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });

export function renderedToModel(x, y) {
  const pan = cy.pan();
  const z = cy.zoom();
  return { x: (x - pan.x) / z, y: (y - pan.y) / z };
}

// --------------------------------------------------------------- selection
export function selectIds(ids, { center = false, add = false } = {}) {
  cy.batch(() => {
    if (!add) cy.nodes().unselect();
    ids.forEach((id) => cy.getElementById(id).select());
  });
  if (center && ids.length) {
    const eles = cy.collection(ids.map((id) => cy.getElementById(id)).filter((x) => x.nonempty()));
    if (eles.nonempty()) cy.animate({ center: { eles }, zoom: Math.max(cy.zoom(), 0.9) }, { duration: 350 });
  }
}

export function selectNeighbors(ids) {
  const col = cy.collection(ids.map((id) => cy.getElementById(id)));
  col.closedNeighborhood("node").select();
}

// ------------------------------------------------------------ highlighting
export function highlight(nodeIds, edgePairs = [], ends = []) {
  pathActive = true;
  cy.batch(() => {
    cy.elements().removeClass("path-node path-edge path-end hl").addClass("faded");
    for (const id of nodeIds) cy.getElementById(id).removeClass("faded").addClass("path-node");
    for (const id of ends) cy.getElementById(id).addClass("path-end");
    for (const [a, b] of edgePairs) {
      const na = cy.getElementById(a);
      const nb = cy.getElementById(b);
      if (na.nonempty() && nb.nonempty()) na.edgesWith(nb).removeClass("faded").addClass("path-edge");
    }
  });
  const eles = cy.collection(nodeIds.map((id) => cy.getElementById(id)).filter((x) => x.nonempty()));
  if (eles.nonempty()) cy.animate({ fit: { eles, padding: 80 } }, { duration: 400 });
}

export function highlightPath(nodes) {
  const pairs = nodes.slice(1).map((n, i) => [nodes[i], n]);
  highlight(nodes, pairs, [nodes[0], nodes[nodes.length - 1]]);
}

export function clearHighlight() {
  pathActive = false;
  cy.batch(() => cy.elements().removeClass("faded path-node path-edge path-end hl hit"));
}

export function focusOn(ids) {
  const col = cy.collection(ids.map((id) => cy.getElementById(id)).filter((x) => x.nonempty()));
  highlight(col.closedNeighborhood("node").map((n) => n.id()), col.connectedEdges().map((e) => [e.data("source"), e.data("target")]), ids);
}

export function searchGraph(q) {
  q = q.trim().toLowerCase();
  cy.nodes().removeClass("hit");
  if (!q) return [];
  const hits = cy.nodes().filter((n) => !n.hasClass("type-hidden")
    && (String(n.data("label")).toLowerCase().includes(q) || String(n.data("value")).toLowerCase().includes(q)));
  hits.addClass("hit");
  return hits.map((n) => n.id());
}

export function centerOn(id) {
  const n = cy.getElementById(id);
  if (n.nonempty()) cy.animate({ center: { eles: n }, zoom: Math.max(cy.zoom(), 1.1) }, { duration: 300 });
}

// --------------------------------------------------------------- analysis
export function applyAnalysisStyle() {
  const a = S.analysis;
  cy.batch(() => {
    cy.nodes().forEach((n) => {
      const ent = S.entities.get(n.id());
      let size = 0;
      if (a && S.sizeBy !== "none") {
        const metric = a[S.sizeBy] || {};
        const max = Math.max(...Object.values(metric), 1e-9);
        const v = metric[n.id()] || 0;
        size = Math.round(24 + 50 * Math.sqrt(v / max));
      }
      n.data("metricSize", size);
      n.data("size", size || baseSize(ent || {}));
      let cc = "";
      if (a && S.colorBy === "community" && a.communities[n.id()] !== undefined) {
        cc = COMMUNITY_COLORS[a.communities[n.id()] % COMMUNITY_COLORS.length];
      } else if (a && S.colorBy === "component" && a.component[n.id()] !== undefined) {
        cc = COMMUNITY_COLORS[a.component[n.id()] % COMMUNITY_COLORS.length];
      }
      n.data("ccolor", cc);
    });
    const chokes = new Set(a && S.showChoke ? a.articulation_points : []);
    cy.nodes().forEach((n) => n.toggleClass("choke", chokes.has(n.id())));
    const bridges = new Set((a && S.showChoke ? a.bridges : []).flatMap(([x, y]) => [`${x}\u0000${y}`, `${y}\u0000${x}`]));
    cy.edges().forEach((e) => e.toggleClass("bridge", bridges.has(`${e.data("source")}\u0000${e.data("target")}`)));
  });
}

export function exportPng(name) {
  const blob = cy.png({ full: true, scale: 2, bg: "#0a0d11", output: "blob", maxWidth: 8000, maxHeight: 8000 });
  download(`${name || "daedalus"}.png`, blob);
}

export const typeLabel = (t) => L(typeInfo(t).label);
