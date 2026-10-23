// User actions on entities and links (create, edit, delete, merge, link...).
import { S, hooks, dropLinksOf, setLinks, linkKey, BOOKMARK_COLORS } from "./state.js";
import * as G from "./graph.js";
import { $, api, copyText, toast, short } from "./util.js";
import { t } from "./i18n.js";
import { confirmDialog, promptDialog } from "./dialogs.js";
import { ingestEntity, ingestLink, markStale } from "./ingest.js";

export async function createEntity({ type, value, parent = null, label = "related", notes, position = null, props }) {
  const r = await api(`/api/cases/${S.caseId}/entities`, {
    method: "POST", body: { type: type || null, value, parent, label, notes: notes || null, props: props || null },
  });
  ingestEntity(r.entity, parent, position);
  if (r.link) ingestLink(r.link);
  G.selectIds([r.entity.id], { center: true });
  hooks.views();
  hooks.palette();
  return r.entity;
}

export async function deleteEntities(ids, { ask = true } = {}) {
  ids = ids.filter((id) => S.entities.has(id));
  if (!ids.length) return;
  if (ask && ids.length > 1 && !(await confirmDialog(t("confirm_delete_n", { n: ids.length })))) return;
  await api(`/api/cases/${S.caseId}/entities/delete`, { method: "POST", body: { ids } });
  for (const id of ids) S.entities.delete(id);
  dropLinksOf(ids);
  G.removeNodes(ids);
  S.selection = S.selection.filter((id) => !ids.includes(id));
  for (const k of ["src", "dst"]) if (ids.includes(S.ariadne[k])) S.ariadne[k] = null;
  markStale();
  G.savePositionsSoon();
  hooks.selection();
  hooks.views();
  hooks.palette();
}

export async function updateEntity(id, body) {
  const r = await api(`/api/cases/${S.caseId}/entities/update`, { method: "POST", body: { id, ...body } });
  if (r.renamed_from) {
    S.entities.delete(r.renamed_from);
    G.removeNodes([r.renamed_from]);
    ingestEntity(r.entity);
    G.cy.edges().remove();
    setLinks([]);
    for (const l of r.links || []) ingestLink(l);
    G.selectIds([r.entity.id], { center: true });
  } else {
    ingestEntity(r.entity);
  }
  hooks.selection();
  hooks.views();
  return r.entity;
}

export async function editValue(id) {
  const ent = S.entities.get(id);
  if (!ent) return;
  const v = await promptDialog({ title: t("edit_value"), value: ent.value, ok: t("save") });
  if (v && v !== ent.value) await updateEntity(id, { value: v });
}

export async function setBookmark(ids, color) {
  for (const id of ids) await updateEntity(id, { bookmark: color });
}

export async function mergeEntities(ids) {
  const ents = ids.map((id) => S.entities.get(id)).filter(Boolean);
  if (ents.length < 2) return;
  const keep = ents.find((e) => e.root) || ents[0];
  if (!(await confirmDialog(t("merge"), t("merge_confirm", { n: ents.length, label: keep.label }), t("merge")))) return;
  const drop = ents.filter((e) => e.id !== keep.id).map((e) => e.id);
  const r = await api(`/api/cases/${S.caseId}/entities/merge`, { method: "POST", body: { keep: keep.id, drop } });
  for (const id of drop) S.entities.delete(id);
  G.removeNodes(drop);
  ingestEntity(r.entity);
  setLinks([]);
  G.cy.edges().remove();
  for (const l of r.links) ingestLink(l);
  G.selectIds([keep.id], { center: true });
  markStale();
  toast(t("merged"), "ok");
  hooks.selection();
  hooks.views();
  hooks.palette();
}

export async function createLink(src, dst, label) {
  const link = await api(`/api/cases/${S.caseId}/links`, { method: "POST", body: { src, dst, label } });
  ingestLink(link);
  toast(t("link_created"), "ok");
  hooks.selection();
}

export async function deleteLink(link) {
  await api(`/api/cases/${S.caseId}/links/delete`, { method: "POST", body: { src: link.src, dst: link.dst, label: link.label } });
  setLinks(S.links.filter((l) => linkKey(l) !== linkKey(link)));
  G.removeEdge(link);
  markStale();
  hooks.selection();
}

export async function relabelLink(link) {
  const label = await promptDialog({ title: t("edit_link"), value: link.label, ok: t("save") });
  if (!label || label === link.label) return;
  await deleteLink(link);
  await createLink(link.src, link.dst, label);
}

export function startLinkMode(id) {
  S.linkFrom = id;
  const b = $("#linkBanner");
  b.textContent = `${short(S.entities.get(id)?.label || "", 40)} → ? · ${t("link_banner")}`;
  b.classList.remove("hidden");
}

export function cancelLinkMode() {
  S.linkFrom = null;
  $("#linkBanner").classList.add("hidden");
}

export async function finishLink(dst) {
  const src = S.linkFrom;
  cancelLinkMode();
  if (!src || src === dst) return;
  const label = await promptDialog({ title: t("label_prompt"), value: "related", ok: t("create") });
  if (label) await createLink(src, dst, label);
}

export async function copyValues(ids) {
  const text = ids.map((id) => S.entities.get(id)?.value).filter(Boolean).join("\n");
  if (await copyText(text)) toast(t("copied"), "ok");
}

export const BOOKMARKS = ["", ...Object.keys(BOOKMARK_COLORS)];
