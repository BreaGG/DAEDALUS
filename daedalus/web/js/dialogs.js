// Modal dialogs: prompt/confirm, new entity and settings.
import { $, api, esc, store } from "./util.js";
import { S, typeInfo } from "./state.js";
import { L, t } from "./i18n.js";

function openDialog(dlg, onClose) {
  return new Promise((resolve) => {
    const handler = () => {
      dlg.removeEventListener("close", handler);
      resolve(onClose(dlg.returnValue));
    };
    dlg.addEventListener("close", handler);
    dlg.returnValue = "";
    dlg.showModal();
  });
}

export function promptDialog({ title, text = "", value = "", ok = "OK", input = true }) {
  const dlg = $("#promptDlg");
  $("#promptTitle").textContent = title;
  $("#promptText").textContent = text;
  const inp = $("#promptInput");
  inp.classList.toggle("hidden", !input);
  inp.value = value;
  $("#promptOk").textContent = ok;
  const p = openDialog(dlg, (rv) => (rv === "ok" ? (input ? inp.value.trim() : true) : null));
  if (input) setTimeout(() => { inp.focus(); inp.select(); }, 30);
  return p;
}

export const confirmDialog = (title, text = "", ok) => promptDialog({ title, text, input: false, ok: ok || t("delete") });

export function typeOptions(selected, { manualOnly = true, auto = false } = {}) {
  const opts = auto ? [`<option value="">${esc(t("auto"))}</option>`] : [];
  const byCat = {};
  for (const [key, info] of Object.entries(S.types)) {
    if (manualOnly && !info.manual) continue;
    (byCat[info.category] ||= []).push([key, info]);
  }
  for (const [cat, items] of Object.entries(byCat)) {
    opts.push(`<optgroup label="${esc(L(S.meta.entity_categories[cat]))}">`);
    for (const [key, info] of items) {
      opts.push(`<option value="${key}" ${key === selected ? "selected" : ""}>${esc(L(info.label))}</option>`);
    }
    opts.push("</optgroup>");
  }
  return opts.join("");
}

export function entityDialog({ type = "username", value = "", parent = null } = {}) {
  const dlg = $("#entityDlg");
  $("#entType").innerHTML = typeOptions(type, { manualOnly: true });
  $("#entValue").value = value;
  $("#entNotes").value = "";
  $("#entLabel").value = "related";
  $("#entLabelRow").classList.toggle("hidden", !parent);
  const p = openDialog(dlg, (rv) => {
    if (rv !== "ok") return null;
    const v = $("#entValue").value.trim();
    if (!v) return null;
    return { type: $("#entType").value, value: v, label: $("#entLabel").value.trim() || "related",
      notes: $("#entNotes").value.trim() };
  });
  setTimeout(() => $("#entValue").focus(), 30);
  return p;
}

export function showSettingsTab(tab) {
  for (const b of document.querySelectorAll("#settingsDlg [data-stab]")) b.classList.toggle("active", b.dataset.stab === tab);
  for (const p of document.querySelectorAll("#settingsDlg [data-spane]")) p.classList.toggle("hidden", p.dataset.spane !== tab);
}

export function initSettingsTabs() {
  $("#settingsDlg .dlg-tabs").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-stab]");
    if (b) showSettingsTab(b.dataset.stab);
  });
}

function renderLanguages(current) {
  const langs = S.meta?.languages || { en: "English", es: "Español" };
  const first = Object.keys(langs)[0];
  $("#langOptions").innerHTML = Object.entries(langs).map(([code, name]) => `
    <label class="lang-card"><input type="radio" name="lang" value="${esc(code)}" ${code === current ? "checked" : ""}>
      <span class="code">${esc(code.toUpperCase())}</span>
      <span class="name">${esc(name)}${code === first ? `<small>${esc(t("lang_default"))}</small>` : ""}</span></label>`).join("");
}

export async function settingsDialog(tab = "general") {
  const dlg = $("#settingsDlg");
  const form = $("#settingsForm");
  const s = await api("/api/settings");
  S.settings = s;
  renderLanguages(s.lang);
  for (const el of form.elements) {
    if (!el.name || !(el.name in s) || el.type === "radio") continue;
    if (el.type === "checkbox") el.checked = !!s[el.name];
    else el.value = s[el.name] ?? "";
  }
  $("#setImages").checked = S.loadImages;
  $("#keysList").innerHTML = Object.entries(s.api_keys).map(([k, info]) => `
    <div class="key-row">
      <div class="lbl">${esc(info.label)} ${info.set ? `<span class="set">● ${esc(t("key_set"))} ${esc(info.masked)}</span>` : ""}
        <a href="${esc(info.url)}" target="_blank" rel="noopener noreferrer">${esc(t("key_get"))} ↗</a></div>
      <input type="password" data-key="${esc(k)}" autocomplete="off" placeholder="${esc(info.set ? t("key_keep") : t("key_ph"))}">
    </div>`).join("");
  showSettingsTab(tab);
  const rv = await openDialog(dlg, (v) => v);
  if (rv !== "save") return null;
  const body = { api_keys: {} };
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "radio") {
      if (el.checked) body[el.name] = el.value;
      continue;
    }
    body[el.name] = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
  }
  if (body.result_limit) body.result_limit = Number(body.result_limit);
  if (body.default_region) body.default_region = body.default_region.toUpperCase();
  for (const inp of $("#keysList").querySelectorAll("input[data-key]")) {
    if (inp.value.trim()) body.api_keys[inp.dataset.key] = inp.value.trim();
  }
  S.loadImages = $("#setImages").checked;
  store.set("loadImages", S.loadImages);
  S.settings = await api("/api/settings", { method: "PUT", body });
  S.limit = S.settings.result_limit;
  store.set("limit", S.limit);
  return S.settings;
}

export async function clearKey(name) {
  S.settings = await api("/api/settings", { method: "PUT", body: { api_keys: { [name]: "" } } });
}

export const typeName = (type) => L(typeInfo(type).label);
