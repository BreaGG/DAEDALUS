// Running transforms and machines, live event stream and the output console.
import { S, hooks } from "./state.js";
import * as G from "./graph.js";
import { $, api, clock, debounce, esc, short, toast } from "./util.js";
import { L, t } from "./i18n.js";
import { ingestEntity, ingestLink } from "./ingest.js";

const MAX_LOG = 600;
const refreshSoon = debounce(() => { hooks.selection(); hooks.views(); hooks.palette(); }, 250);

export async function runTransforms(ids, names = null) {
  if (!ids.length) return;
  const r = await api(`/api/cases/${S.caseId}/run`, {
    method: "POST", body: { entity_ids: ids, transforms: names, limit: S.limit },
  });
  const title = names && names.length === 1 ? L(S.transforms[names[0]]?.title) : t("run_all");
  watch(r.job_id, title);
}

export async function runMachine(ids, machine, depth = 2) {
  if (!ids.length) return;
  const r = await api(`/api/cases/${S.caseId}/machine`, {
    method: "POST", body: { entity_ids: ids, machine, depth, limit: S.limit },
  });
  log({ status: "info", transform: L(S.machines[machine]?.title), message: t("run_machine") });
  watch(r.job_id, L(S.machines[machine]?.title));
}

function watch(jobId, title) {
  const job = { id: jobId, caseId: S.caseId, title, total: 0, done: 0, created: 0, finished: false };
  S.jobs.set(jobId, job);
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  job.es = es;
  es.onmessage = (m) => {
    try { handle(job, JSON.parse(m.data)); } catch (e) { console.error(e); }
  };
  es.onerror = () => {
    es.close();
    if (!job.finished) {
      job.finished = true;
      S.jobs.delete(job.id);
      log({ status: "error", message: t("lost_stream") });
      hooks.reload?.();
    }
    renderProgress();
  };
  renderProgress();
}

function handle(job, ev) {
  const here = job.caseId === S.caseId;
  switch (ev.type) {
    case "plan":
      job.total += ev.runs || 0;
      break;
    case "stage":
      job.total += ev.runs;
      log({ status: "info", transform: job.title, message: t("stage", { i: ev.index + 1, n: ev.runs, f: ev.frontier }) });
      break;
    case "run_start": {
      const key = `${ev.entity_id}|${ev.transform}`;
      S.running.set(key, (S.running.get(key) || 0) + 1);
      if (here) G.setScanning(ev.entity_id, true);
      break;
    }
    case "entity":
      if (!here) break;
      if (ingestEntity(ev.entity, ev.parent)) job.created++;
      if (S.selection.includes(ev.entity.id)) refreshSoon();
      break;
    case "link":
      if (here) ingestLink(ev.link);
      break;
    case "run": {
      const r = ev.run;
      job.done++;
      const key = `${r.entity_id}|${r.transform}`;
      const left = (S.running.get(key) || 1) - 1;
      if (left > 0) S.running.set(key, left);
      else S.running.delete(key);
      if (here) {
        S.runs.push(r);
        const busy = [...S.running.keys()].some((k) => k.startsWith(`${r.entity_id}|`));
        if (!busy) G.setScanning(r.entity_id, false);
        log({ status: r.status, entityId: r.entity_id, transform: L(S.transforms[r.transform]?.title) || r.transform,
          message: r.message });
      }
      refreshSoon();
      break;
    }
    case "error":
      log({ status: "error", transform: job.title, message: ev.message });
      break;
    case "done":
      finish(job, ev);
      break;
    default:
  }
  renderProgress();
}

function finish(job, ev) {
  job.finished = true;
  job.es?.close();
  S.jobs.delete(job.id);
  for (const k of [...S.running.keys()]) if (!S.running.get(k)) S.running.delete(k);
  const msg = ev.cancelled ? t("job_cancelled") : t("job_done", { created: job.created, s: ev.seconds ?? "?" });
  log({ status: ev.cancelled ? "skipped" : "ok", transform: job.title, message: msg });
  if (job.caseId === S.caseId) {
    G.cy.nodes(".scanning").removeClass("scanning");
    if (S.autoLayout && job.created > 0) G.runLayout(S.layoutName, { fit: G.cy.nodes().length < 250 });
    else G.savePositionsSoon();
    toast(msg, ev.cancelled ? "info" : "ok");
  }
  refreshSoon();
}

export async function cancelAll() {
  const mine = [...S.jobs.values()].filter((j) => j.caseId === S.caseId);
  await Promise.all(mine.map((j) => api(`/api/jobs/${j.id}/cancel`, { method: "POST" }).catch(() => {})));
}

export function closeAll() {
  for (const j of S.jobs.values()) j.es?.close();
  S.jobs.clear();
  S.running.clear();
  renderProgress();
}

export function renderProgress() {
  const jobs = [...S.jobs.values()].filter((j) => j.caseId === S.caseId);
  const el = $("#jobProgress");
  $("#cancelJobs").classList.toggle("hidden", !jobs.length);
  if (!jobs.length) {
    el.innerHTML = "";
    return;
  }
  const total = jobs.reduce((a, j) => a + j.total, 0);
  const done = jobs.reduce((a, j) => a + j.done, 0);
  const created = jobs.reduce((a, j) => a + j.created, 0);
  const pct = total ? Math.round((100 * done) / total) : 5;
  el.innerHTML = `<span class="spin"></span><div class="bar"><i style="width:${pct}%"></i></div>
    <span>${esc(t("job_running", { done, total, created }))}</span>`;
}

const ICON = { ok: "✓", empty: "∅", error: "✕", skipped: "»", info: "·" };

export function log({ status = "info", entityId = null, transform = "", message = "" }) {
  const box = $("#log");
  const ent = entityId ? S.entities.get(entityId) : null;
  const row = document.createElement("div");
  row.className = "log-line";
  row.innerHTML = `<span class="t">${clock()}</span><span class="st-${esc(status)}">${ICON[status] || "·"}</span>
    <span class="ent" ${ent ? `data-id="${esc(ent.id)}"` : ""} title="${esc(ent?.value || "")}">${esc(ent ? short(ent.label, 40) : "")}</span>
    <span class="tr" title="${esc(transform)}">${esc(transform)}</span><span class="msg" title="${esc(message)}">${esc(message)}</span>`;
  const stick = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  box.append(row);
  while (box.childElementCount > MAX_LOG) box.firstElementChild.remove();
  if (stick) box.scrollTop = box.scrollHeight;
}
