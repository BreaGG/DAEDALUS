// Apply entities and links coming from the API to state + canvas.
import { S, hooks, pushLink } from "./state.js";
import * as G from "./graph.js";

export function markStale() {
  S.analysisStale = true;
  hooks.stale();
}

export function ingestEntity(ent, parent = null, position = null) {
  S.entities.set(ent.id, ent);
  const created = G.upsertNode(ent, parent, position);
  if (created) markStale();
  return created;
}

export function ingestLink(link) {
  if (!pushLink(link)) return false;
  G.addEdge(link);
  markStale();
  return true;
}
