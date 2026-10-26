// Spanish / English UI strings. Transform and entity names come bilingual from the API.
import { $$ } from "./util.js";

const DICT = {
  es: {
    tagline: "análisis de vínculos · osint",
    case_open: "Investigación abierta", new_case: "Nueva", case_actions: "Acciones de la investigación",
    quick_ph: "Añade una entidad: alias, correo, teléfono, nombre, dominio, IP, URL, hash, cartera…",
    entity_type: "Tipo", auto: "Automático", add: "Añadir", investigate: "Investigar",
    import: "Importar", export: "Exportar", settings: "Ajustes",
    palette: "Paleta de entidades", filter: "Filtrar…", machines: "Máquinas", image_analysis: "Imagen (EXIF/GPS)",
    upload_image: "Suelta o elige una foto para extraer sus metadatos",
    tab_graph: "Grafo", tab_table: "Tabla", tab_map: "Mapa", tab_timeline: "Cronología", tab_notes: "Notas",
    layout: "Disposición", layout_organic: "Orgánico", layout_hierarchical: "Jerárquico", layout_radial: "Radial",
    layout_circular: "Circular", layout_concentric: "Concéntrico", layout_block: "Bloques por tipo",
    relayout: "Reorganizar", auto_layout: "auto", auto_layout_tip: "Reorganizar el grafo al terminar cada transform",
    ariadne: "Hilo de Ariadna", ariadne_tip: "Encontrar los caminos que conectan dos entidades",
    ariadne_sub: "Caminos entre dos entidades", analysis: "Análisis", analysis_tip: "Centralidad, comunidades y puntos de paso",
    analysis_sub: "La estructura del laberinto", graph_search: "Buscar en el grafo…", link_labels: "etiquetas",
    empty_title: "Todo laberinto tiene salida",
    empty_p1: "Escribe arriba un alias, correo, teléfono, nombre, dominio, IP, URL, hash o cartera, o arrastra una entidad desde la paleta.",
    empty_p2: "Clic derecho sobre un nodo para lanzar transforms. Selecciona dos nodos y usa el Hilo de Ariadna para encontrar los caminos que los unen.",
    fit: "Encuadrar", origin: "Origen", target: "Destino", use_selection: "Usar el nodo seleccionado",
    max_paths: "Máx. caminos", max_hops: "Máx. saltos", respect_direction: "Respetar la dirección de los enlaces",
    find_paths: "Buscar caminos", clear: "Limpiar", connect_title: "Conectar selección",
    connect_help: "Con 2 o más nodos seleccionados, resalta el subgrafo mínimo que los une.",
    connect_btn: "Conectar seleccionados", compute: "Calcular",
    table_filter: "Filtrar entidades…", delete_marked: "Eliminar marcadas", all_types: "Todos los tipos",
    map_empty: "No hay entidades con coordenadas en esta investigación.", notes_ph: "Notas de la investigación (se guardan solas)…",
    output: "Salida", cancel: "Cancelar", detail: "Detalle", transforms: "Transforms",
    new_entity: "Nueva entidad", value: "Valor", link_label: "Etiqueta del enlace", notes: "Notas", create: "Crear",
    settings_sub: "Todo se guarda en tu equipo, en la carpeta de datos de DAEDALUS.",
    set_limit: "Resultados máximos por transform", set_machine: "Máximo de entidades por máquina",
    set_timeout: "Tiempo por sitio en el barrido de alias (s)", set_region: "País por defecto para teléfonos (ISO, ej. ES, MX)",
    set_sherlock: "Ampliar el barrido de alias con la base de datos de Sherlock (400+ sitios)",
    set_nsfw: "Incluir sitios para adultos en el barrido", set_ssrf: "Bloquear direcciones privadas en los transforms web (recomendado)",
    set_images: "Cargar imágenes remotas (avatares) automáticamente",
    api_keys: "Claves API", api_keys_help: "Todas opcionales. Sin clave, el transform que la necesita se omite.",
    save: "Guardar", saved: "Guardado", key_set: "configurada", key_get: "Conseguir clave", key_ph: "pega la clave", key_keep: "•••• (déjalo vacío para mantenerla)",
    // runtime
    no_cases: "Primera investigación", rename_case: "Renombrar investigación", delete_case: "Eliminar investigación",
    confirm_delete_case: "¿Eliminar «{name}» y todo su contenido? No se puede deshacer.", case_name: "Nombre de la investigación",
    export_json: "JSON (DAEDALUS)", export_graphml: "GraphML (Gephi, yEd…)", export_csv: "CSV de entidades", export_links: "CSV de enlaces",
    export_png: "Imagen PNG", imported: "Investigación importada", added: "Añadida: {label}",
    run_all: "Ejecutar todos los transforms", run_all_n: "Ejecutar todos ({n})", run: "Ejecutar",
    machines_menu: "Máquinas", machine_depth: "Niveles", run_machine: "Lanzar máquina",
    ari_from: "Hilo de Ariadna: origen", ari_to: "Hilo de Ariadna: destino", select_neighbors: "Seleccionar vecinos",
    focus: "Aislar vecindario", similar: "Entidades parecidas", link_to: "Enlazar con…", merge: "Fusionar en una",
    bookmark: "Marcador", copy_value: "Copiar valor", open_link: "Abrir enlace", delete: "Eliminar", delete_n: "Eliminar {n} entidades",
    add_here: "Añadir entidad aquí", select_all: "Seleccionar todo", edit_value: "Editar valor", delete_link: "Eliminar enlace",
    edit_link: "Cambiar etiqueta", link_banner: "Haz clic en la entidad de destino · Esc para cancelar",
    link_created: "Enlace creado", copied: "Copiado", confirm_delete_n: "¿Eliminar {n} entidades?",
    n_selected: "{n} entidades seleccionadas", nothing_selected: "Selecciona una entidad para ver sus datos.",
    case_summary: "{e} entidades · {l} enlaces", properties: "Propiedades", add_property: "Propiedad",
    prop_name: "Nombre de la propiedad", prop_value: "Valor", links_ext: "Enlaces", connections: "Conexiones",
    sources: "Fuentes", history: "Transforms ejecutados", dates: "Fechas", unverified: "Por comprobar a mano",
    unverified_help: "Estos sitios bloquearon la comprobación automática. Ábrelos para verificarlo tú.",
    load_image: "Cargar imagen", root: "semilla", types: "Tipos", no_transforms: "No hay transforms para esta selección.",
    result_limit: "Límite", needs_key: "Necesita clave: {k}", never_run: "", filter_transforms: "Filtrar transforms…",
    job_running: "{done}/{total} transforms · {created} entidades nuevas", job_done: "Terminado: {created} entidades nuevas en {s} s",
    job_cancelled: "Cancelado", stage: "Etapa {i}: {n} transforms sobre {f} entidades", lost_stream: "Se perdió la conexión con el trabajo; recargando…",
    paths_found: "{n} camino(s)", no_path: "No hay ningún camino entre estas entidades.", pick_two: "Elige un origen y un destino.",
    hops: "{n} saltos", show_all: "Mostrar todos", unreachable_pairs: "{n} pares sin conexión",
    an_entities: "entidades", an_links: "enlaces", an_components: "componentes", an_communities: "comunidades",
    an_modularity: "modularidad", an_density: "densidad", size_by: "Tamaño según", color_by: "Color según",
    m_none: "nada", m_degree: "grado", m_betweenness: "intermediación", m_pagerank: "PageRank",
    c_type: "tipo", c_community: "comunidad", c_component: "componente", show_choke: "Resaltar puntos de paso",
    choke_help: "Entidades (y enlaces) cuya eliminación parte el grafo: los pasillos obligados del laberinto.",
    hubs: "Centros del laberinto", similar_pairs: "¿La misma identidad?", similar_help: "Entidades del mismo tipo que comparten vecinos.",
    shared: "{n} en común", none_found: "Nada por aquí.", analysis_stale: "El grafo cambió: pulsa Calcular para actualizar.",
    analysis_empty: "Pulsa Calcular para analizar la estructura del grafo.", choke_points: "Puntos de paso",
    merge_confirm: "¿Fusionar {n} entidades en «{label}»?", merged: "Entidades fusionadas",
    dropped: "Suelta para crear", image_uploaded: "Imagen analizada", timeline_empty: "Aún no hay fechas en esta investigación.",
    col_type: "Tipo", col_value: "Entidad", col_links: "Enlaces", col_sources: "Fuentes", col_added: "Añadida",
    status_ok: "ok", status_empty: "vacío", status_error: "error", status_skipped: "omitido",
    unknown_error: "Error", value_required: "Escribe un valor", label_prompt: "Etiqueta del enlace", rename_prompt: "Nuevo valor",
    open_profile: "Abrir", more: "más…", unknown: "desconocido", nb_count: "{n} conexiones",
    set_tab_general: "General", set_tab_language: "Idioma", lang_title: "Idioma de la interfaz",
    lang_help: "Elige el idioma de DAEDALUS. Se guarda en los ajustes de esta instalación.",
    lang_default: "predeterminado", lang_note: "Los datos que devuelven las fuentes (títulos de páginas, perfiles, descripciones…) se muestran en su idioma original.",
    lang_switch: "Cambiar idioma",
    shortcuts: "Atajos", by_type: "Entidades por tipo",
    help_html: "<div class=\"kb\"><span><kbd>Clic dcho.</kbd></span><span>Transforms</span></div><div class=\"kb\"><span><kbd>Doble clic</kbd></span><span>Panel de transforms</span></div><div class=\"kb\"><span><kbd>Ctrl/⌘</kbd>+clic</span><span>Añadir a la selección</span></div><div class=\"kb\"><span><kbd>Shift</kbd>+arrastrar</span><span>Seleccionar un área</span></div><div class=\"kb\"><span><kbd>Supr</kbd></span><span>Borrar</span></div><div class=\"kb\"><span><kbd>Esc</kbd></span><span>Limpiar</span></div><div class=\"kb\"><span><kbd>F</kbd></span><span>Encuadrar</span></div><div class=\"kb\"><span><kbd>Ctrl+A</kbd></span><span>Seleccionar todo</span></div>",
  },
  en: {
    tagline: "link analysis · osint",
    case_open: "Open investigation", new_case: "New", case_actions: "Investigation actions",
    quick_ph: "Add an entity: alias, email, phone, name, domain, IP, URL, hash, wallet…",
    entity_type: "Type", auto: "Auto", add: "Add", investigate: "Investigate",
    import: "Import", export: "Export", settings: "Settings",
    palette: "Entity palette", filter: "Filter…", machines: "Machines", image_analysis: "Image (EXIF/GPS)",
    upload_image: "Drop or pick a photo to extract its metadata",
    tab_graph: "Graph", tab_table: "Table", tab_map: "Map", tab_timeline: "Timeline", tab_notes: "Notes",
    layout: "Layout", layout_organic: "Organic", layout_hierarchical: "Hierarchical", layout_radial: "Radial",
    layout_circular: "Circular", layout_concentric: "Concentric", layout_block: "Blocks by type",
    relayout: "Re-layout", auto_layout: "auto", auto_layout_tip: "Re-layout the graph when each transform finishes",
    ariadne: "Ariadne's thread", ariadne_tip: "Find the paths that connect two entities",
    ariadne_sub: "Paths between two entities", analysis: "Analysis", analysis_tip: "Centrality, communities and choke points",
    analysis_sub: "The structure of the labyrinth", graph_search: "Search the graph…", link_labels: "labels",
    empty_title: "Every labyrinth has a way out",
    empty_p1: "Type an alias, email, phone, name, domain, IP, URL, hash or wallet above, or drag an entity from the palette.",
    empty_p2: "Right-click a node to run transforms. Select two nodes and use Ariadne's thread to find the paths between them.",
    fit: "Fit", origin: "Origin", target: "Target", use_selection: "Use the selected node",
    max_paths: "Max paths", max_hops: "Max hops", respect_direction: "Follow link direction",
    find_paths: "Find paths", clear: "Clear", connect_title: "Connect selection",
    connect_help: "With 2 or more nodes selected, highlights the smallest subgraph joining them.",
    connect_btn: "Connect selected", compute: "Compute",
    table_filter: "Filter entities…", delete_marked: "Delete checked", all_types: "All types",
    map_empty: "No entities with coordinates in this investigation.", notes_ph: "Investigation notes (saved automatically)…",
    output: "Output", cancel: "Cancel", detail: "Detail", transforms: "Transforms",
    new_entity: "New entity", value: "Value", link_label: "Link label", notes: "Notes", create: "Create",
    settings_sub: "Everything is stored on your machine, in the DAEDALUS data folder.",
    set_limit: "Max results per transform", set_machine: "Max entities per machine",
    set_timeout: "Per-site timeout in the alias sweep (s)", set_region: "Default country for phones (ISO, e.g. US, ES)",
    set_sherlock: "Extend the alias sweep with the Sherlock database (400+ sites)",
    set_nsfw: "Include adult sites in the sweep", set_ssrf: "Block private addresses in web transforms (recommended)",
    set_images: "Load remote images (avatars) automatically",
    api_keys: "API keys", api_keys_help: "All optional. Without a key, the transform that needs it is skipped.",
    save: "Save", saved: "Saved", key_set: "set", key_get: "Get a key", key_ph: "paste the key", key_keep: "•••• (leave empty to keep)",
    no_cases: "First investigation", rename_case: "Rename investigation", delete_case: "Delete investigation",
    confirm_delete_case: "Delete “{name}” and everything in it? This cannot be undone.", case_name: "Investigation name",
    export_json: "JSON (DAEDALUS)", export_graphml: "GraphML (Gephi, yEd…)", export_csv: "Entities CSV", export_links: "Links CSV",
    export_png: "PNG image", imported: "Investigation imported", added: "Added: {label}",
    run_all: "Run all transforms", run_all_n: "Run all ({n})", run: "Run",
    machines_menu: "Machines", machine_depth: "Levels", run_machine: "Start machine",
    ari_from: "Ariadne: set as origin", ari_to: "Ariadne: set as target", select_neighbors: "Select neighbours",
    focus: "Isolate neighbourhood", similar: "Similar entities", link_to: "Link to…", merge: "Merge into one",
    bookmark: "Bookmark", copy_value: "Copy value", open_link: "Open link", delete: "Delete", delete_n: "Delete {n} entities",
    add_here: "Add entity here", select_all: "Select all", edit_value: "Edit value", delete_link: "Delete link",
    edit_link: "Change label", link_banner: "Click the target entity · Esc to cancel",
    link_created: "Link created", copied: "Copied", confirm_delete_n: "Delete {n} entities?",
    n_selected: "{n} entities selected", nothing_selected: "Select an entity to see its data.",
    case_summary: "{e} entities · {l} links", properties: "Properties", add_property: "Property",
    prop_name: "Property name", prop_value: "Value", links_ext: "Links", connections: "Connections",
    sources: "Sources", history: "Transforms run", dates: "Dates", unverified: "To check by hand",
    unverified_help: "These sites blocked the automatic check. Open them to verify yourself.",
    load_image: "Load image", root: "seed", types: "Types", no_transforms: "No transforms for this selection.",
    result_limit: "Limit", needs_key: "Needs key: {k}", never_run: "", filter_transforms: "Filter transforms…",
    job_running: "{done}/{total} transforms · {created} new entities", job_done: "Done: {created} new entities in {s} s",
    job_cancelled: "Cancelled", stage: "Stage {i}: {n} transforms on {f} entities", lost_stream: "Lost the job stream; reloading…",
    paths_found: "{n} path(s)", no_path: "There is no path between these entities.", pick_two: "Pick an origin and a target.",
    hops: "{n} hops", show_all: "Show all", unreachable_pairs: "{n} unconnected pairs",
    an_entities: "entities", an_links: "links", an_components: "components", an_communities: "communities",
    an_modularity: "modularity", an_density: "density", size_by: "Size by", color_by: "Colour by",
    m_none: "nothing", m_degree: "degree", m_betweenness: "betweenness", m_pagerank: "PageRank",
    c_type: "type", c_community: "community", c_component: "component", show_choke: "Highlight choke points",
    choke_help: "Entities (and links) whose removal splits the graph: the labyrinth's forced passages.",
    hubs: "Centres of the labyrinth", similar_pairs: "Same identity?", similar_help: "Same-type entities sharing neighbours.",
    shared: "{n} shared", none_found: "Nothing here.", analysis_stale: "The graph changed: press Compute to refresh.",
    analysis_empty: "Press Compute to analyse the structure of the graph.", choke_points: "Choke points",
    merge_confirm: "Merge {n} entities into “{label}”?", merged: "Entities merged",
    dropped: "Drop to create", image_uploaded: "Image analysed", timeline_empty: "No dates in this investigation yet.",
    col_type: "Type", col_value: "Entity", col_links: "Links", col_sources: "Sources", col_added: "Added",
    status_ok: "ok", status_empty: "empty", status_error: "error", status_skipped: "skipped",
    unknown_error: "Error", value_required: "Type a value", label_prompt: "Link label", rename_prompt: "New value",
    open_profile: "Open", more: "more…", unknown: "unknown", nb_count: "{n} connections",
    set_tab_general: "General", set_tab_language: "Language", lang_title: "Interface language",
    lang_help: "Choose the language of DAEDALUS. It is saved in this installation's settings.",
    lang_default: "default", lang_note: "Data returned by the sources (page titles, profiles, descriptions…) is shown in its original language.",
    lang_switch: "Switch language",
    shortcuts: "Shortcuts", by_type: "Entities by type",
    help_html: "<div class=\"kb\"><span><kbd>Right-click</kbd></span><span>Transforms</span></div><div class=\"kb\"><span><kbd>Double-click</kbd></span><span>Transforms panel</span></div><div class=\"kb\"><span><kbd>Ctrl/⌘</kbd>+click</span><span>Add to selection</span></div><div class=\"kb\"><span><kbd>Shift</kbd>+drag</span><span>Select an area</span></div><div class=\"kb\"><span><kbd>Del</kbd></span><span>Delete</span></div><div class=\"kb\"><span><kbd>Esc</kbd></span><span>Clear</span></div><div class=\"kb\"><span><kbd>F</kbd></span><span>Fit</span></div><div class=\"kb\"><span><kbd>Ctrl+A</kbd></span><span>Select all</span></div>",
  },
};

// link labels produced by transforms (English in the database), translated for display
const LINKS_ES = {
  related: "relacionado", "has account": "tiene cuenta", subdomain: "subdominio", "subdomain of": "subdominio de",
  registrant: "registrante", registrar: "registrador", "admin contact": "contacto admin", "tech contact": "contacto técnico",
  "billing contact": "contacto de facturación", "abuse contact": "contacto de abuso", "registrant address": "dirección del registrante",
  "located in": "ubicada en", website: "sitio web", mentions: "menciona", "links to": "enlaza a",
  "links to profile": "enlaza al perfil", uses: "usa", "exposed in": "expuesto en", name: "nombre", "lives in": "vive en",
  "works at": "trabaja en", "verified account": "cuenta verificada", "linked account": "cuenta vinculada",
  "public email": "correo público", "commit email": "correo de commits", "commit author": "autor de commits",
  "local part": "parte local", "email domain": "dominio del correo", "possible alias": "alias posible",
  "mentioned at": "mencionado en", "described at": "descrito en", "vulnerable to": "vulnerable a",
  "in netblock": "en el bloque", "announced by": "anunciado por", announces: "anuncia", "operated by": "operado por",
  owner: "titular", "hosted on": "alojado en", "hosted at": "alojado en", "redirects to": "redirige a",
  "archived file": "fichero archivado", "security contact": "contacto de seguridad", "sent to": "envió a",
  "registered in": "registrado en", "DMARC report": "informe DMARC", "taken at": "tomada en", "proves domain": "demuestra el dominio",
  "scanned page": "página escaneada", "served from": "servida desde", "owned by": "propiedad de", serves: "sirve",
  "email at": "correo en", host: "host", hostname: "nombre de host", artist: "autor", "windows author": "autor (Windows)",
  "camera owner": "dueño de la cámara", copyright: "copyright",
};

const PROPS_ES = {
  platform: "plataforma", username: "usuario", display_name: "nombre visible", bio: "bio", location: "ubicación",
  created: "creada", followers: "seguidores", country: "país", country_code: "código de país", city: "ciudad",
  region: "región", isp: "ISP", timezone: "zona horaria", timezones: "zonas horarias", registrar: "registrador",
  registered: "registrado", expires: "caduca", last_changed: "último cambio", status: "estado", title: "título",
  description: "descripción", technologies: "tecnologías", generator: "generador", open_ports: "puertos abiertos",
  tags: "etiquetas", cpes: "CPEs", valid: "válido", e164: "E.164", international: "formato internacional",
  line_type: "tipo de línea", carrier: "operador", region_code: "región", provider: "proveedor",
  free_provider: "proveedor gratuito", domain_accepts_mail: "el dominio acepta correo", mx_records: "registros MX",
  disposable: "desechable", balance: "saldo", tx_count: "transacciones", total_received: "total recibido",
  last_activity: "última actividad", chain: "cadena", accepts_mail: "acepta correo", txt_records: "registros TXT",
  spf: "SPF", dmarc: "DMARC", dmarc_policy: "política DMARC", verification_tokens: "tokens de verificación",
  subdomain_count: "nº de subdominios", first_archived: "primera captura", last_archived: "última captura",
  sites_checked: "sitios comprobados", accounts_found: "cuentas encontradas", verification: "verificación",
  date: "fecha", records: "registros", data_classes: "datos expuestos", industry: "sector", role: "rol",
  network_name: "red", network_range: "rango", allocated: "asignada", name: "nombre", announced_prefixes: "prefijos anunciados",
  precision: "precisión", address: "dirección", filename: "archivo", dimensions: "dimensiones", camera_make: "marca",
  camera_model: "modelo", taken: "tomada", software: "software", artist: "autor", known_file: "fichero conocido",
  algorithm: "algoritmo", severity: "gravedad", cvss: "CVSS", published: "publicado", position: "cargo",
  confidence: "confianza", email_pattern: "patrón de correo", karma: "karma", guessed: "supuesto", category: "categoría",
  first_certificate: "primer certificado", mx_priority: "prioridad MX", version: "versión", scanned: "escaneado",
  server: "servidor", final_url: "URL final", snippet: "fragmento", query: "consulta", search_engine: "buscador",
  about: "acerca de", kind: "tipo", is_contract: "es contrato", ens_name: "nombre ENS", label: "etiqueta",
  posts: "publicaciones", fields: "campos", info: "info", hireable: "contratable", public_repos: "repos públicos",
  updated: "actualizado", commit_author: "autor del commit", abuse_score: "puntuación de abuso", abuse_reports: "denuncias",
  usage_type: "tipo de uso", is_tor: "Tor", last_reported: "última denuncia", services: "servicios", os: "SO",
  last_update: "última actualización", vt_malicious: "VT maliciosos", vt_suspicious: "VT sospechosos",
  vt_harmless: "VT inofensivos", vt_reputation: "VT reputación", vt_categories: "VT categorías", vt_tags: "VT etiquetas",
};

// English is DAEDALUS' default; the chosen language is a server setting (Settings → Language).
export const LANGS = ["en", "es"];
let lang = "en";

export const getLang = () => lang;

export function setLang(l) {
  lang = LANGS.includes(l) ? l : "en";
  document.documentElement.lang = lang;
  applyI18n();
}

export function t(key, vars = {}) {
  let s = DICT[lang][key] ?? DICT.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

export const L = (obj) => (obj && typeof obj === "object" ? obj[lang] || obj.en || "" : String(obj ?? ""));

export function linkLabel(label) {
  if (lang !== "es") return label;
  return LINKS_ES[label] || label;
}

export function propLabel(key) {
  if (lang === "es" && PROPS_ES[key]) return PROPS_ES[key];
  return key.replace(/^_+/, "").replace(/_/g, " ");
}

export function applyI18n(root = document) {
  for (const el of $$("[data-i18n]", root)) el.textContent = t(el.dataset.i18n);
  for (const el of $$("[data-i18n-ph]", root)) el.placeholder = t(el.dataset.i18nPh);
  for (const el of $$("[data-i18n-title]", root)) el.title = t(el.dataset.i18nTitle);
}
