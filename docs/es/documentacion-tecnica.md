# Documentación técnica de DAEDALUS

Autor: **Alejandro Brea**

Cómo está construido DAEDALUS, cómo ejecutarlo y desplegarlo, su API HTTP y cómo ampliarlo con tus propios transforms.
Para el uso diario de la interfaz consulta la [guía de usuario](guia-de-usuario.md); para la lista de entidades,
transforms y máquinas, la [referencia](transforms.md).

**Contenido**

1. [Arquitectura](#1-arquitectura)
2. [Instalación](#2-instalación)
3. [Ejecución y configuración](#3-ejecución-y-configuración)
4. [Despliegue](#4-despliegue)
5. [Modelo de seguridad](#5-modelo-de-seguridad)
6. [Modelo de datos](#6-modelo-de-datos)
7. [Motor de transforms](#7-motor-de-transforms)
8. [API HTTP](#8-api-http)
9. [Algoritmos de grafos](#9-algoritmos-de-grafos)
10. [Ampliar DAEDALUS](#10-ampliar-daedalus)
11. [Frontend](#11-frontend)
12. [Desarrollo](#12-desarrollo)

---

## 1. Arquitectura

```
 Navegador (aplicación de una página, sin compilación)
   │  REST (JSON)            ▲ Server-Sent Events (progreso de los trabajos en directo)
   ▼                         │
 App FastAPI ── api.py ──────┤
   │                         │
   ├── engine.py ── trabajos asíncronos ── transforms/* ──► fuentes y APIs públicas (httpx, DNS, WHOIS)
   ├── graphalgo.py  (caminos, centralidad, comunidades, puntos de paso)
   └── store.py ──► SQLite (daedalus.db, WAL)     settings.json     plugins/*.py
```

- **Un solo proceso.** El servidor web, el ejecutor de trabajos y la base de datos viven en un único proceso de Python
  (FastAPI + uvicorn, asyncio). Los trabajos se guardan en memoria, así que **ejecuta exactamente una instancia**.
- **Backend** (`daedalus/`): Python ≥ 3.11 con FastAPI, httpx, dnspython, phonenumbers y Pillow. No necesita servicios
  externos aparte de las propias fuentes OSINT.
- **Frontend** (`daedalus/web/`): módulos ES sin frameworks, con Cytoscape.js (grafo), fcose/dagre (disposiciones) y
  Leaflet (mapa) incluidos en el repositorio. Funciona sin conexión salvo las teselas del mapa.

| Módulo | Responsabilidad |
|---|---|
| `__main__.py` | Punto de entrada de la línea de comandos y salvaguardas de despliegue (puerto, contraseña, volumen, cambio de usuario). |
| `api.py` | `create_app()`: rutas HTTP, autenticación Basic opcional, ficheros estáticos, importar/exportar. |
| `engine.py` | Trabajos, el `Context` que recibe cada transform, límites de resultados, máquinas, protección SSRF. |
| `store.py` | Persistencia SQLite de investigaciones, entidades, enlaces y ejecuciones. |
| `entities.py` | Catálogo de entidades, detección de tipo, normalización e identificadores. |
| `graphalgo.py` | Algoritmos de grafos sin dependencias. |
| `transforms/` | Transforms incluidos por familias, el registro, las máquinas y el cargador de plugins. |
| `config.py` | Rutas, persistencia de ajustes, catálogo de claves API, idiomas. |
| `exif.py` | Extracción de metadatos de fotos. |
| `webutil.py` | Análisis de HTML, patrones de URLs de perfiles sociales, utilidades DNS. |

## 2. Instalación

```bash
git clone https://github.com/BreaGG/DAEDALUS.git && cd DAEDALUS
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .            # o bien: pip install -e ".[dev]" para pytest + ruff
```

`start.sh` / `start.bat` hacen lo mismo (crean `.venv` e instalan `requirements.txt`) y arrancan la aplicación.
El paquete también se puede construir como wheel (`pip wheel .`); los ficheros web van dentro.

## 3. Ejecución y configuración

```bash
daedalus [--host HOST] [--port PUERTO] [--data-dir CARPETA] [--no-browser]
python -m daedalus ...        # equivalente
```

### Opciones y variables de entorno

| Opción | Variable de entorno | Por defecto | Significado |
|---|---|---|---|
| `--host` | `DAEDALUS_HOST` | `127.0.0.1` | Interfaz de escucha. `0.0.0.0` lo expone en la red (pon una contraseña). |
| `--port` | `DAEDALUS_PORT`, después `PORT` | `8787` | Puerto. `PORT` es el que inyectan Railway, Render, Fly… |
| `--data-dir` | ver abajo | ver abajo | Dónde se guardan investigaciones y ajustes. |
| `--no-browser` | — | no | No abrir una pestaña del navegador al arrancar. |
| — | `DAEDALUS_PASSWORD` | vacía | Activa la autenticación HTTP Basic en toda la aplicación (cualquier usuario, esta contraseña). |
| — | `DAEDALUS_ALLOW_PUBLIC` | — | `1` permite arrancar en Railway sin contraseña (no recomendado). |
| — | `DAEDALUS_RUN_AS` | — | Si arranca como root, se adueña de la carpeta de datos y pasa a este usuario (la imagen Docker usa `daedalus`). |

### Carpeta de datos

Se elige en este orden; gana la primera que exista:

1. `--data-dir`
2. `DAEDALUS_DATA_DIR`
3. `RAILWAY_VOLUME_MOUNT_PATH` (la define Railway al montar un volumen)
4. `DAEDALUS_DEFAULT_DATA_DIR` (`/data` en la imagen Docker)
5. `./data` junto al código fuente
6. `~/.daedalus`

Contenido:

| Fichero | Qué es |
|---|---|
| `daedalus.db` (+ `-wal`, `-shm`) | Base de datos SQLite con todas las investigaciones. |
| `settings.json` | Ajustes distintos de los predeterminados, **incluidas las claves API en texto plano**. |
| `plugins/*.py` | Tus transforms y máquinas propios (se cargan al arrancar). |
| `sherlock.json` | Caché de la lista de sitios de Sherlock, si esa opción está activada. |

**Copias de seguridad**: copia la carpeta con DAEDALUS parado, o usa `sqlite3 daedalus.db ".backup copia.db"` mientras
funciona. Cada investigación se puede exportar a JSON desde la interfaz (o con `GET /api/cases/{id}/export`).
**Actualizar**: descarga la nueva versión y reinicia; las tablas que falten se crean y los datos se conservan.

## 4. Despliegue

DAEDALUS necesita un proceso que se mantenga encendido, un disco persistente, una sola instancia y salida a internet
(HTTPS, DNS en el 53 y WHOIS en el TCP 43). Las plataformas serverless como Vercel o Netlify Functions no sirven: los
trabajos siguen después de la respuesta HTTP, el progreso se emite desde memoria y la base de datos es un fichero.

### Local

`./start.sh` (o `daedalus`). Escucha en `127.0.0.1:8787`, accesible sólo desde tu equipo.

### Docker Compose

```bash
DAEDALUS_PASSWORD='una-cadena-larga-y-aleatoria' docker compose up -d --build
```

El `docker-compose.yml` incluido publica el puerto sólo en `127.0.0.1` y monta `./data` en `/data`. La imagen arranca
como root sólo lo justo para adueñarse del volumen montado y después funciona como el usuario sin privilegios
`daedalus`. El contenedor declara un `HEALTHCHECK` sobre `/healthz`.

### Railway

El repositorio incluye `railway.toml` (build con el Dockerfile, healthcheck en `/healthz`, una réplica, sin
suspensión).

1. **New Project → Deploy from GitHub repo** y elige el repositorio (y la rama que quieras desplegar).
2. **Variables**: añade `DAEDALUS_PASSWORD` (por ejemplo `openssl rand -base64 24`). Sin ella la aplicación se detiene
   con un error que lo explica, así que una URL pública nunca queda como un proxy abierto.
3. **Volumes**: añade un volumen al servicio (cualquier ruta de montaje). DAEDALUS usa `RAILWAY_VOLUME_MOUNT_PATH`
   automáticamente. Sin volumen se avisa en los logs y los datos se pierden en cada redespliegue.
4. **Networking → Generate Domain** y abre la URL `*.up.railway.app`.

Notas: el Dockerfile no tiene la instrucción `VOLUME` a propósito (Railway la rechaza). Un redespliegue interrumpe los
trabajos en marcha. Las peticiones a las fuentes salen desde IPs de centro de datos de Railway, que algunas redes
sociales bloquean más.

### VPS detrás de un proxy inverso

Ejecuta Docker Compose como arriba y pon delante un proxy con TLS. Con Caddy:

```
daedalus.tudominio.com {
    reverse_proxy 127.0.0.1:8787
}
```

Caddy transmite los Server-Sent Events sin configuración extra. Con Nginx, desactiva el buffering para la API
(`proxy_buffering off;`; DAEDALUS también envía `X-Accel-Buffering: no`) y sube `proxy_read_timeout` por encima del
trabajo más largo que esperes.

## 5. Modelo de seguridad

- **Un usuario / contraseña compartida.** No hay cuentas ni roles. Quien tenga la contraseña puede leer y modificar
  todas las investigaciones y los ajustes (incluidas las claves API).
- **La autenticación Basic** protege todas las rutas salvo `/healthz`. Las contraseñas incorrectas se responden con un
  segundo de retraso. Sírvelo siempre por **HTTPS** cuando salga de tu equipo.
- **Salvaguarda en Railway**: la aplicación no arranca en Railway sin `DAEDALUS_PASSWORD`.
- **Protección SSRF**: los transforms que descargan URLs aportadas por el usuario (`to_website`, `web_page_scan`,
  `security_txt`) resuelven antes el host y rechazan direcciones privadas, de loopback, link-local, reservadas y
  multicast, comprobando de nuevo cada redirección. Se controla en *Ajustes → Bloquear direcciones privadas* (activado
  por defecto).
- **XSS**: todo valor que viene de las fuentes se escapa antes de insertarlo en la página; sólo se pintan enlaces
  `http(s)`; los enlaces externos usan `rel="noopener noreferrer nofollow"`. Las imágenes remotas sólo se cargan bajo
  demanda y con `referrerpolicy="no-referrer"`.
- **Secretos en disco**: las claves API están en `settings.json` en texto plano. Protege la carpeta de datos (o el
  volumen).
- **Los plugins** son código Python arbitrario que se ejecuta con los privilegios de la aplicación. Instala sólo
  plugins de confianza.
- Las respuestas llevan `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`.

## 6. Modelo de datos

Tablas SQLite (las crea `store.py`):

| Tabla | Clave | Columnas |
|---|---|---|
| `cases` | `id` | `name`, `notes`, `layout` (JSON: posiciones de los nodos y disposición), `created`, `updated` |
| `entities` | `(case_id, id)` | `type`, `value`, `props` (JSON), `notes`, `bookmark`, `root`, `created`, `updated` |
| `links` | `(case_id, src, dst, label)` | `transform` (qué transform lo creó, o `manual`), `created` |
| `runs` | `id` | `case_id`, `entity_id`, `transform`, `status`, `message`, `found`, `started`, `finished` |

**Los identificadores de entidad** son `tipo:valor` tras normalizar (`domain:example.com`, `email:jane@example.com`).
La normalización pasa a minúsculas correos, dominios, alias y hashes, canoniza IPs y CIDR, quita el formato de los
teléfonos, etcétera; los tipos de texto libre (persona, organización, ubicación, frase, cuenta, url) se comparan sin
distinguir mayúsculas. Añadir una entidad que ya existe fusiona sus propiedades en lugar de duplicarla. Un enlace es
único por `(origen, destino, etiqueta)`.

**Las propiedades** son JSON libre. Las listas se fusionan sin duplicados, los objetos clave a clave y los valores
simples se sobrescriben. Las claves que empiezan por `_` están reservadas para la interfaz y no aparecen en la tabla de
propiedades:

| Clave | Formato | Para qué |
|---|---|---|
| `_sources` | `["Título del transform", …]` | Qué transforms produjeron o enriquecieron la entidad. |
| `_links` | `[["etiqueta", "https://…"], …]` | Enlaces externos que muestra el inspector. |
| `_dates` | `[["qué pasó", "AAAA-MM-DD"], …]` | Eventos de la cronología. |
| `_lat`, `_lon` | números | Posición en el mapa. |
| `_image` | URL | Avatar o captura (se carga bajo demanda). |
| `_unverified` | `[["sitio", "https://…"], …]` | Sitios por comprobar a mano (barrido de alias). |
| `_aliases` | `["valor antiguo", …]` | Valores de las entidades fusionadas en esta. |

## 7. Motor de transforms

- **Trabajos.** `POST /run` o `/machine` devuelve un `job_id` al momento; el trabajo sigue en segundo plano y emite
  eventos que el navegador lee mediante Server-Sent Events. Los trabajos viven en memoria (se conservan los 30 últimos
  terminados); las ejecuciones y los resultados se guardan según ocurren, así que no se pierde nada si el navegador se
  desconecta.
- **Concurrencia.** Hasta 10 transforms a la vez por trabajo; el barrido de alias hace hasta 25 peticiones en paralelo.
  El cliente HTTP compartido sigue redirecciones, usa 20 s de tiempo máximo (10 s para conectar) y un User-Agent de
  navegador.
- **Cada ejecución** recibe un `Context` ligado a una entidad y un transform. Primero se comprueban las claves API
  obligatorias (si falta alguna → `skipped`). La ejecución tiene un tiempo máximo (45 s por defecto, más en fuentes
  lentas) y un límite de resultados: pasado `limit`, `ctx.add()` devuelve `None` y la ejecución se marca como
  truncada.
- **Estados.** `ok` (añadió entidades o propiedades), `empty`, `skipped` (se lanzó `Skip`: falta clave, límite de
  peticiones, entrada no soportada) y `error` (error de red, tiempo agotado o excepción; la traza completa va al log
  del servidor).
- **Ejecutar todos** lanza todos los transforms con `default` activado que acepten la entidad.
- **Máquinas.** La etapa *n* ejecuta sus transforms sobre las entidades que produjo la etapa *n−1* (las semillas en la
  primera), sin repetir nunca el mismo transform sobre la misma entidad. La expansión se detiene cuando se han
  expandido `machine_max_entities` entidades. La máquina genérica *Laberinto* repite «todos los transforms por defecto»
  durante 1-4 niveles.
- **Cancelar.** `POST /api/jobs/{id}/cancel` cancela la tarea asyncio; los resultados ya guardados se mantienen.

## 8. API HTTP

Todo lo que hace la interfaz pasa por esta API JSON, así que puedes automatizar DAEDALUS. Los cuerpos son JSON salvo
que se indique. Con contraseña, envía credenciales HTTP Basic (cualquier usuario). Los errores devuelven
`{"detail": "..."}` con estado 400 (entrada incorrecta), 401 (autenticación), 404 (caso, entidad o trabajo
desconocido), 413 (subida demasiado grande) o 422 (validación del esquema).

### Objetos

```jsonc
// entidad
{"id": "email:jane@example.com", "type": "email", "value": "jane@example.com", "label": "jane@example.com",
 "props": {"_sources": ["Manual"]}, "notes": "", "bookmark": "", "root": true, "created": 1792757057.3, "updated": 1792757057.3}
// enlace
{"src": "username:jane", "dst": "email:jane@example.com", "label": "public email", "transform": "github_profile"}
// ejecución
{"id": 7, "case_id": 1, "entity_id": "ip:203.0.113.9", "transform": "shodan_internetdb", "status": "ok",
 "message": "2 result(s)", "found": 2, "started": 1792757060.1, "finished": 1792757061.4}
```

### Endpoints

| Método y ruta | Cuerpo / consulta | Devuelve |
|---|---|---|
| `GET /healthz` | — | `{"ok": true, "version"}` (sin autenticación) |
| `GET /api/meta` | — | tipos y categorías de entidad, transforms (con `ready` = claves presentes), máquinas, idiomas, plugins |
| `POST /api/detect` | `{"value"}` | `{"type"}` tipo de entidad detectado |
| `GET /api/settings` | — | ajustes, con las claves API enmascaradas (`{"set", "masked", "label", "url"}`) |
| `PUT /api/settings` | cualquier subconjunto de ajustes, `{"api_keys": {"shodan": "…"}}` (cadena vacía borra una clave) | ajustes |
| `GET /api/cases` | — | `[{"id", "name", "created", "updated", "entities", "links"}]` |
| `POST /api/cases` | `{"name", "notes"?}` | caso |
| `GET /api/cases/{id}` | — | `{"case", "entities", "links", "runs"}` |
| `PATCH /api/cases/{id}` | `{"name"?, "notes"?, "layout"?}` | caso |
| `DELETE /api/cases/{id}` | — | `{"ok": true}` |
| `POST /api/cases/{id}/entities` | `{"value", "type"?, "props"?, "notes"?, "parent"?, "label"?}` | `{"entity", "created", "link"}`; con `parent` se crea un enlace manual parent → entidad |
| `POST /api/cases/{id}/entities/update` | `{"id", "value"?, "props"?, "replace"?, "notes"?, "bookmark"?}` | `{"entity", "renamed_from", "links"}`; `props` fusiona, `replace` sobrescribe (`null` borra una clave), un `value` nuevo renombra/fusiona |
| `POST /api/cases/{id}/entities/delete` | `{"ids": [...]}` | `{"deleted"}` |
| `POST /api/cases/{id}/entities/merge` | `{"keep", "drop": [...]}` | `{"entity", "links"}` |
| `POST /api/cases/{id}/links` | `{"src", "dst", "label"}` | enlace (`transform: "manual"`) |
| `POST /api/cases/{id}/links/delete` | `{"src", "dst", "label"}` | `{"ok"}` |
| `GET /api/cases/{id}/runs` | `?entity=<id>` opcional | `[ejecución]` |
| `POST /api/cases/{id}/run` | `{"entity_ids", "transforms"?, "limit"?}` (sin `transforms` = todos los por defecto) | `{"job_id"}` |
| `POST /api/cases/{id}/machine` | `{"entity_ids", "machine", "depth"?: 2, "limit"?}` | `{"job_id"}` |
| `GET /api/jobs/{job_id}/events` | — | `text/event-stream` (ver abajo) |
| `POST /api/jobs/{job_id}/cancel` | — | `{"ok"}` |
| `POST /api/cases/{id}/paths` | `{"src", "dst", "k"?: 5 (1-25), "max_len"? (1-30), "directed"?: false}` | `{"paths": [{"nodes", "length", "hops": [{"src", "dst", "labels", "forward"}]}]}` |
| `POST /api/cases/{id}/connect` | `{"ids", "directed"?}` (≤ 25 ids) | `{"nodes", "edges", "unreachable"}` |
| `GET /api/cases/{id}/analysis` | — | `stats`, `degree`, `betweenness`, `pagerank`, `communities`, `component`, `articulation_points`, `bridges`, `hubs`, `similar` |
| `POST /api/cases/{id}/similar` | `{"ids": [id]}` | `{"similar": [{"id", "shared", "jaccard"}]}` |
| `POST /api/cases/{id}/upload` | multipart `file` (imagen ≤ 40 MB) | `{"entity"}` (imagen + hash, ubicación, personas) |
| `GET /api/cases/{id}/export` | `?format=json\|graphml\|csv\|links-csv` | descarga del fichero |
| `POST /api/import` | multipart `file` (JSON de DAEDALUS) | el caso nuevo |

### Eventos de los trabajos en directo

`GET /api/jobs/{job_id}/events` es un flujo Server-Sent Events. Cada mensaje es `data: <json>`; cada 15 s se envía un
comentario `: ping`. El flujo reproduce el trabajo desde su primer evento, así que al reconectar no se pierde nada, y
termina tras `done` o `error`.

| `type` | Campos | Cuándo |
|---|---|---|
| `plan` | `runs` (transforms) o `machine`, `stages` | Trabajo planificado. |
| `stage` | `index`, `runs`, `frontier` | Empieza una etapa de una máquina. |
| `run_start` | `entity_id`, `transform` | Un transform empieza sobre una entidad. |
| `entity` | `entity`, `created`, `parent`? | Se añadió una entidad (`parent` = la entidad de la que cuelga) o cambiaron sus propiedades. |
| `link` | `link` | Un enlace nuevo. |
| `run` | `run` | Un transform terminó (con estado y mensaje). |
| `error` | `message` | El trabajo falló. |
| `done` | `created`, `seconds`, `cancelled`? | El trabajo terminó. |

### Ejemplo: automatizar una investigación rápida

```bash
API=http://127.0.0.1:8787/api
CASE=$(curl -s -X POST $API/cases -H 'content-type: application/json' -d '{"name":"automatizada"}' | jq .id)
ID=$(curl -s -X POST $API/cases/$CASE/entities -H 'content-type: application/json' \
      -d '{"value":"example.com"}' | jq -r .entity.id)
JOB=$(curl -s -X POST $API/cases/$CASE/machine -H 'content-type: application/json' \
      -d "{\"entity_ids\":[\"$ID\"],\"machine\":\"domain_footprint\"}" | jq -r .job_id)
curl -sN $API/jobs/$JOB/events | grep --line-buffered '"type": "done"' | head -1
curl -s "$API/cases/$CASE/export?format=graphml" -o example.graphml
```

Añade `-u cualquiera:$DAEDALUS_PASSWORD` a cada llamada si hay contraseña.

## 9. Algoritmos de grafos

Todos están en `graphalgo.py`, sin dependencias externas, y trabajan sobre el multigrafo de la investigación (los
enlaces paralelos cuentan como una arista; la dirección se ignora salvo que se pida `directed`).

| Función | Algoritmo | Notas |
|---|---|---|
| Hilo de Ariadna | *k* caminos más cortos sin ciclos de Yen sobre BFS | Ordenados por saltos; longitud máxima y modo dirigido opcionales. |
| Conectar selección | Unión de los caminos más cortos entre cada pareja | Hasta 25 entidades. |
| Intermediación | Brandes, normalizada a 0-1 | Se muestrea desde 300 orígenes cuando el grafo supera las 1.500 entidades. |
| PageRank | Iteración de potencias, amortiguación 0,85 | Dirigido, con tratamiento de nodos sin salida. |
| Comunidades | Optimización de modularidad de Louvain | Determinista; comunidades numeradas de mayor a menor. |
| Puntos de paso | Puntos de articulación y puentes de Tarjan | DFS iterativo (sin límite de recursión). |
| ¿La misma identidad? | Vecinos compartidos entre entidades del mismo tipo | Al menos 2 vecinos en común y sin enlace directo; se ignoran nodos con más de 150 vecinos; las 20 mejores por número y Jaccard. |

## 10. Ampliar DAEDALUS

### Escribir un transform

```python
from daedalus.transforms import L, Skip, Transform, register


@register
class ToKeybase(Transform):
    name = "my_keybase"                       # identificador único (pon prefijo en tus plugins para evitar choques)
    title = L("To Keybase proofs", "A pruebas de Keybase")
    description = L("Accounts proven on Keybase.", "Cuentas demostradas en Keybase.")
    category = "social"                       # dns, infrastructure, web, identity, social, search,
                                              # location, crypto, threat o utility
    inputs = ("username",)                    # tipos de entidad que acepta
    outputs = ("account",)                    # informativo (aparece en la referencia)
    sources = ("Keybase",)
    keys = ()                                 # claves API obligatorias (sin ellas se omite)
    optional_keys = ()
    timeout = 45                              # segundos
    default = True                            # incluirlo en «Ejecutar todos» y en la máquina Laberinto

    async def run(self, ctx):
        status, data = await ctx.get_json("https://keybase.io/_/api/1.0/user/lookup.json",
                                          params={"usernames": ctx.value})
        if status != 200:
            raise Skip(f"Keybase HTTP {status}")
        them = (data or {}).get("them") or [None]
        for proof in ((them[0] or {}).get("proofs_summary") or {}).get("all", []):
            if ctx.add("account", proof["service_url"], {"platform": proof["proof_type"]}, label="proves") is None:
                break                          # se alcanzó el límite de resultados
```

Sobrescribe `applies(self, entity) -> bool` para filtrar con más detalle (los transforms de carteras sólo aceptan
direcciones BTC/ETH).

### La API de `Context`

| Miembro | Descripción |
|---|---|
| `ctx.value`, `ctx.props`, `ctx.entity` | Valor, propiedades y registro completo de la entidad de entrada. |
| `ctx.http` | `httpx.AsyncClient` compartido. Usa siempre `await`; no bloquees el bucle de eventos (envuelve las librerías bloqueantes en `asyncio.to_thread`). |
| `await ctx.get_json(url, **kw)` | GET que devuelve `(estado, json_o_None)` sin lanzar excepciones por errores HTTP. |
| `ctx.add(tipo, valor, props=None, label="", parent=None, reverse=False)` | Crea o fusiona una entidad y la enlaza desde la entidad de entrada (o desde `parent`); `reverse=True` invierte el enlace. Devuelve su id, o `None` si el valor está vacío o se alcanzó el límite. |
| `ctx.enrich(props, eid=None)` | Fusiona propiedades en la entidad de entrada (o en `eid`). |
| `ctx.log(mensaje)` | Sustituye el mensaje de estado por defecto de la ejecución. |
| `ctx.key(nombre)` / `ctx.require_key(nombre)` | Lee una clave API / la lee u omite la ejecución. Añade los nombres nuevos a `API_KEYS` en `config.py`. |
| `await ctx.assert_public(url)` | Protección SSRF: lanza `Skip` si la URL apunta a una dirección privada (llámala antes de descargar URLs del usuario). |
| `ctx.limit`, `ctx.settings`, `ctx.engine` | Límite de resultados, ajustes y motor (p. ej. `ctx.engine.data_dir`). |
| `raise Skip("motivo")` | Termina la ejecución con estado `skipped` y ese mensaje. |

Usa las propiedades reservadas de la [sección 6](#6-modelo-de-datos) (`_links`, `_dates`, `_lat`/`_lon`, `_image`…)
para que la interfaz muestre tus datos en el inspector, la cronología y el mapa.

### Escribir una máquina

```python
from daedalus.transforms import L, Machine, machine

machine(Machine(
    "my_email_pivot",
    L("Email pivot", "Pivote de correo"),
    L("Alias, Gravatar and breaches, then profiles of the aliases.", "Alias, Gravatar y filtraciones, y luego perfiles."),
    ("email",),                               # tipos de entrada sugeridos
    [["email_to_alias", "gravatar", "xposedornot"], ["username_profiles", "github_profile"]],
))
```

Con `chain=False` cada etapa se ejecuta sobre todas las entidades vistas hasta el momento, no sólo sobre lo que produjo
la anterior.

### Plugins

Deja ficheros `.py` en `<carpeta de datos>/plugins/` y reinicia. Cada fichero se importa una vez al arrancar (se saltan
los que empiezan por `_`); si un plugin falla al importarse, se registra en el log y se ignora. Los transforms que añade
un plugin aparecen en `GET /api/meta` → `plugins`. Ver
[`examples/plugins/email_hashes.py`](../../examples/plugins/email_hashes.py).

### Probarlo

`tests/conftest.py` incluye un `Router` que simula HTTP según expresiones regulares de URL y un ayudante
`run_transform()`. En un módulo de test dentro de `tests/` (con el módulo de tu transform importado para que quede
registrado):

```python
from .conftest import run_transform, values

def test_my_keybase(engine_env, router):
    router.add(r"keybase\.io/_/api", json_body={"them": [{"proofs_summary": {"all": [
        {"proof_type": "github", "service_url": "https://github.com/jane"}]}}]})
    graph, run, _ = run_transform(engine_env, router, "my_keybase", "username", "jane")
    assert run["status"] == "ok"
    assert values(graph, "account") == ["https://github.com/jane"]
```

Si cambias los transforms incluidos, regenera también la referencia con `python scripts/gen_docs.py` (un test falla si
está desactualizada).

## 11. Frontend

`daedalus/web/index.html` carga las librerías incluidas como scripts clásicos y `js/main.js` como módulo ES. No hay
empaquetador: edita un fichero y recarga.

| Módulo | Responsabilidad |
|---|---|
| `main.js` | Arranque, gestión de investigaciones, conexión de todos los paneles, atajos, arrastrar y soltar. |
| `state.js` | Estado compartido `S` y `hooks` (callbacks de refresco, para evitar ciclos de imports). |
| `graph.js` | Configuración de Cytoscape, estilos, colocación de nodos, disposiciones, resaltado, guardado de posiciones. |
| `jobs.js` | Lanzar transforms/máquinas, consumir el flujo de eventos, la consola Salida. |
| `actions.js`, `ingest.js` | Acciones de crear/editar/eliminar/fusionar/enlazar; aplicar los resultados de la API al estado y al lienzo. |
| `inspector.js` | Paneles Detalle y Transforms. |
| `menu.js` | Menús contextuales (nodo, enlace, lienzo, exportar, investigación). |
| `ariadne.js` | Paneles del Hilo de Ariadna y de análisis. |
| `views.js` | Tabla, mapa, cronología y notas. |
| `dialogs.js` | Nueva entidad, avisos/confirmaciones y el diálogo de Ajustes. |
| `i18n.js`, `icons.js`, `util.js` | Traducciones, iconos de entidades, utilidades de DOM y HTTP. |

- **Traducciones**: el texto estático usa los atributos `data-i18n`, `data-i18n-ph` (placeholder) y `data-i18n-title`;
  añade cada clave nueva a `DICT.en` y a `DICT.es` en `i18n.js`. Los nombres de entidades, transforms y máquinas ya
  llegan bilingües desde la API (`L(en, es)` en Python).
- **Depuración**: `window.DAEDALUS` expone `state` y el módulo `graph` (`DAEDALUS.graph.cy` es la instancia de
  Cytoscape).

## 12. Desarrollo

```bash
pip install -e ".[dev]"
pytest -q                      # más de 80 tests; todo el HTTP está simulado, no hace falta red
ruff check daedalus tests      # lint
python scripts/gen_docs.py     # regenera docs/*/transforms.md tras cambiar transforms o máquinas
```

La integración continua (GitHub Actions) ejecuta ruff y pytest en Python 3.11, 3.12 y 3.13. Estructura del
repositorio:

```
daedalus/            paquete de la aplicación (backend + web/)
docs/                guía de usuario, documentación técnica, referencia generada, capturas
examples/            investigación de demostración y un plugin de ejemplo
scripts/gen_docs.py  generador de la referencia
tests/               tests de pytest
Dockerfile, docker-compose.yml, railway.toml, start.sh, start.bat
```
