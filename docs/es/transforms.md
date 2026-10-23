# Referencia de entidades, transforms y máquinas

Autor: **Alejandro Brea**

> Generado a partir del código por `scripts/gen_docs.py`. No lo edites a mano.

[Entidades](#entidades) · [Transforms](#transforms) · [Máquinas](#máquinas) · [Claves API](#claves-api)

## Entidades

Cada nodo del grafo es una entidad de uno de estos tipos. Los que tienen ejemplo se pueden escribir en la barra de alta rápida y se reconocen solos; los demás se crean desde la paleta o los generan los transforms.

| Tipo | Id | Categoría | Se crea a mano | Se detecta a partir de |
|---|---|---|---|---|
| Persona | `person` | Identidad | sí | `John Smith` |
| Alias | `username` | Identidad | sí | `teolabrys` |
| Correo | `email` | Identidad | sí | `jane@example.com` |
| Teléfono | `phone` | Identidad | sí | `+34 612 345 678` |
| Cuenta online | `account` | Identidad | sí | sólo desde paleta / menú |
| Organización | `organization` | Identidad | sí | sólo desde paleta / menú |
| Dominio | `domain` | Infraestructura | sí | `example.com` |
| Nombre DNS | `hostname` | Infraestructura | sí | `mail.example.com` |
| Dirección IP | `ip` | Infraestructura | sí | `203.0.113.17` |
| Bloque de red | `netblock` | Infraestructura | sí | `203.0.113.0/24` |
| Sistema autónomo | `asn` | Infraestructura | sí | `AS64500` |
| URL | `url` | Web | sí | `https://example.com/about` |
| Código de seguimiento | `tracking_code` | Web | sí | `G-ABCD123456` |
| Ubicación | `location` | Ubicación | sí | `40.4168, -3.7038` |
| Cartera cripto | `crypto` | Cripto y finanzas | sí | `bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4` |
| Hash | `hash` | Artefactos | sí | `d41d8cd98f00b204e9800998ecf8427e` |
| Imagen | `image` | Artefactos | no | se crea al subir una foto |
| Frase | `phrase` | Artefactos | sí | `selling access to a vpn` |
| Filtración | `breach` | Amenazas | no | la crean los transforms de filtraciones |
| Vulnerabilidad | `vulnerability` | Amenazas | sí | `CVE-2021-44228` |

## Transforms

Un transform toma una entidad y devuelve entidades relacionadas y/o nuevas propiedades. Haz clic derecho sobre una entidad (o una selección) para lanzarlos. *Ejecutar todos* lanza los marcados como **por defecto**.

**46** transforms en 9 categorías; 41 no necesitan clave API.

### DNS

#### A dirección IP [DNS]

Resuelve los registros A y AAAA.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `dns_resolve` | Dominio, Nombre DNS | Dirección IP | DNS | ninguna | sí | 45 s |

#### A dominio padre

Dominio registrable de un nombre DNS.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `hostname_to_domain` | Nombre DNS | Dominio | — | ninguna | sí | 45 s |

#### A dominios en la misma IP

IP inversa (capa gratuita de HackerTarget).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `reverse_ip` | Dirección IP | Nombre DNS | HackerTarget | ninguna | sí | 45 s |

#### A nombre DNS [PTR]

Búsqueda DNS inversa.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `reverse_dns` | Dirección IP | Nombre DNS | DNS | ninguna | sí | 45 s |

#### A nombres DNS e IPs [HackerTarget]

Búsqueda pasiva de hosts (gratis: 50 consultas/día).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `hackertarget_hosts` | Dominio | Nombre DNS, Dirección IP | HackerTarget | ninguna | — | 45 s |

#### A servidores de correo [MX]

Registros MX del dominio.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `dns_mx` | Dominio | Nombre DNS | DNS | ninguna | sí | 45 s |

#### A servidores de nombres [NS]

Registros NS del dominio.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `dns_ns` | Dominio | Nombre DNS | DNS | ninguna | sí | 45 s |

#### A subdominios [Certificate Transparency]

Nombres encontrados en certificados TLS (crt.sh, con CertSpotter de respaldo).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `crtsh_subdomains` | Dominio | Nombre DNS | crt.sh, CertSpotter | ninguna | sí | 90 s |

#### A TXT / SPF / DMARC

Lee los TXT: los include de SPF pasan a dominios e IPs, las direcciones de informes DMARC a correos y los tokens de verificación de terceros se guardan como propiedades.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `dns_txt` | Dominio | Dominio, Nombre DNS, Dirección IP, Bloque de red, Correo | DNS | ninguna | sí | 45 s |

### Infraestructura

#### A bloque de red y AS [RIPEstat]

Prefijo anunciado y AS de origen de una IP, o el AS de origen de un bloque.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `ripestat_network` | Dirección IP, Bloque de red | Bloque de red, Sistema autónomo | RIPEstat | ninguna | sí | 45 s |

#### A bloque de red y titular [RDAP]

Asignación de red, organización titular y contacto de abuso.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `rdap_ip` | Dirección IP | Bloque de red, Organización, Correo | RDAP | ninguna | sí | 45 s |

#### A bloques anunciados y titular

Titular de un sistema autónomo y los prefijos que anuncia.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `asn_prefixes` | Sistema autónomo | Bloque de red, Organización | RIPEstat | ninguna | sí | 45 s |

#### A datos de registro [RDAP/WHOIS]

Registrador, fechas, contactos y servidores de nombres. Usa WHOIS si el TLD no tiene RDAP.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `rdap_domain` | Dominio | Organización, Correo, Teléfono, Persona, Nombre DNS, Ubicación | RDAP, WHOIS | ninguna | sí | 45 s |

#### A puertos, hosts y CVEs [InternetDB]

InternetDB gratuita de Shodan: puertos abiertos, CPEs, etiquetas, hosts y vulnerabilidades.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `shodan_internetdb` | Dirección IP | Nombre DNS, Vulnerabilidad | Shodan InternetDB | ninguna | sí | 45 s |

#### A ubicación e ISP [GeoIP]

Geolocalización aproximada, ISP y sistema autónomo.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `ip_geolocation` | Dirección IP | Ubicación, Sistema autónomo, Organización | ipwho.is, ip-api.com | ninguna | sí | 45 s |

### Web

#### A contactos de seguridad [security.txt]

Contactos publicados en /.well-known/security.txt.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `security_txt` | Dominio | Correo, URL | HTTP | ninguna | sí | 45 s |

#### A entidades de la página

Descarga la página y extrae correos, teléfonos, perfiles sociales, códigos de seguimiento, tecnologías y los dominios a los que enlaza.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `web_page_scan` | URL | Correo, Teléfono, Cuenta online, Código de seguimiento, Dominio | HTTP | ninguna | sí | 45 s |

#### A ficheros archivados [Wayback Machine]

URLs archivadas del dominio que parecen documentos, copias de seguridad o configuraciones.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `wayback_urls` | Dominio | URL | Internet Archive | ninguna | — | 90 s |

#### A historial archivado [Wayback Machine]

Primera y última captura en Internet Archive.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `wayback` | Dominio, Nombre DNS, URL | propiedades de la entidad de entrada | Internet Archive | ninguna | sí | 45 s |

#### A nombre DNS / dominio

Host de una URL.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `url_to_host` | URL | Dominio, Nombre DNS, Dirección IP | — | ninguna | sí | 45 s |

#### A sitio web

Comprueba si el nombre sirve una web por HTTPS o HTTP.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `to_website` | Dominio, Nombre DNS | URL | HTTP | ninguna | sí | 45 s |

### Identidad

#### A alias (parte local)

La parte antes de la @, cuando parece un alias personal.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `email_to_alias` | Correo | Alias | — | ninguna | sí | 45 s |

#### A alias probables (permutaciones)

Alias típicos construidos con el nombre (jperez, juan.perez...). Son suposiciones: verifícalos con el barrido de cuentas.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `person_to_aliases` | Persona | Alias | — | ninguna | — | 45 s |

#### A correos y personas [Hunter.io]

Direcciones publicadas del dominio, con nombres y cargos.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `hunter_domain` | Dominio | Correo, Persona, Organización | Hunter.io | `hunter` | sí | 45 s |

#### A dominio

Dominio de la dirección. Los proveedores gratuitos se anotan pero no se añaden, para que no creen puentes falsos entre personas que no tienen relación.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `email_to_domain` | Correo | Dominio | — | ninguna | sí | 45 s |

#### A operador, región y tipo de línea

Análisis sin conexión con libphonenumber: validez, país, operador, tipo de línea y zona horaria.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `phone_info` | Teléfono | Ubicación | libphonenumber | ninguna | sí | 45 s |

#### Validar dirección [MX]

¿El dominio acepta correo? ¿Es un proveedor desechable?

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `email_validate` | Correo | propiedades de la entidad de entrada | — | ninguna | sí | 45 s |

### Redes y cuentas

#### A alias

Alias usado en la cuenta.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `account_to_alias` | Cuenta online | Alias | — | ninguna | sí | 45 s |

#### A cuentas [barrido de sitios]

Comprueba el alias en ~75 sitios (400+ con la base de Sherlock activada en ajustes). Cada acierto se contrasta con un alias aleatorio para descartar sitios que responden «sí» a todo.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `username_sweep` | Alias | Cuenta online | 75+ sites, Sherlock DB (optional) | ninguna | sí | 180 s |

#### A perfil de GitHub y correos de commits

Datos del perfil y los correos de autor que aparecen en sus commits públicos.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `github_profile` | Alias | Cuenta online, Persona, Organización, Ubicación, URL, Correo | GitHub API | opcional: `github` | sí | 60 s |

#### A perfil de Gravatar

Perfil público de Gravatar: nombre, ubicación, avatar y cuentas verificadas.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `gravatar` | Correo | Cuenta online, Persona, Ubicación, URL | Gravatar | ninguna | sí | 45 s |

#### A perfiles detallados

Perfiles públicos completos (nombre, bio, ubicación, enlaces, fecha de alta) de GitLab, Keybase, Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram y X.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `username_profiles` | Alias | Cuenta online, Persona, Ubicación, URL, Correo, Dominio | GitLab, Keybase, Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram, X | ninguna | sí | 90 s |

### Buscadores

#### A dorks de búsqueda (enlaces)

Consultas preparadas de Google / Bing / DuckDuckGo / Yandex que se adjuntan a la entidad para revisarlas a mano.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `dork_links` | Persona, Alias, Correo, Teléfono, Dominio, Organización, Frase | propiedades de la entidad de entrada | — | ninguna | — | 45 s |

#### A entradas de Wikidata

Elementos coincidentes en Wikidata (personajes públicos, empresas, lugares).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `wikidata` | Persona, Organización, Ubicación | URL | Wikidata | ninguna | sí | 45 s |

#### A menciones web [buscador]

Páginas que mencionan el valor. Usa Serper (Google) o Brave si hay clave; si no, DuckDuckGo.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `web_search` | Persona, Alias, Correo, Teléfono, Frase, Organización, Código de seguimiento, Cartera cripto, Hash, Dominio | URL | Serper, Brave, DuckDuckGo | opcional: `serper`, `brave` | sí | 45 s |

### Ubicación

#### A coordenadas / dirección [OSM]

Sitúa la ubicación en el mapa (o pone nombre a unas coordenadas).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `geocode` | Ubicación | propiedades de la entidad de entrada | OpenStreetMap Nominatim | ninguna | sí | 45 s |

### Blockchain

#### A carteras contraparte

Direcciones que enviaron o recibieron fondos de esta cartera en sus últimas transacciones.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `wallet_counterparties` | Cartera cripto | Cartera cripto | Blockstream, Blockscout | ninguna | — | 45 s |

#### A saldo y actividad

Saldo, número de transacciones y primera/última actividad (Bitcoin con Blockstream, Ethereum con Blockscout).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `wallet_info` | Cartera cripto | propiedades de la entidad de entrada | Blockstream, Blockscout | ninguna | sí | 45 s |

### Amenazas

#### A denuncias de abuso [AbuseIPDB]

Puntuación de abuso y denuncias de los últimos 90 días.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `abuseipdb` | Dirección IP | propiedades de la entidad de entrada | AbuseIPDB | `abuseipdb` | sí | 45 s |

#### A detalles del CVE [NVD]

Descripción, puntuación CVSS y fecha.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `cve_info` | Vulnerabilidad | propiedades de la entidad de entrada | NIST NVD | ninguna | sí | 45 s |

#### A fichero conocido [CIRCL hashlookup]

¿El hash corresponde a un fichero conocido (NSRL y otros conjuntos)?

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `hash_lookup` | Hash | propiedades de la entidad de entrada | CIRCL hashlookup | ninguna | sí | 45 s |

#### A filtraciones [Have I Been Pwned]

Filtraciones de HIBP (clave de pago).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `hibp` | Correo | Filtración | Have I Been Pwned | `hibp` | sí | 45 s |

#### A filtraciones [XposedOrNot]

Filtraciones públicas en las que aparece la dirección (gratis, sin clave).

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `xposedornot` | Correo | Filtración | XposedOrNot | ninguna | sí | 45 s |

#### A páginas escaneadas [urlscan.io]

Escaneos públicos de urlscan.io del dominio o IP: URLs, IPs y servidores vistos.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `urlscan` | Dominio, Nombre DNS, Dirección IP | URL, Dirección IP, Dominio | urlscan.io | opcional: `urlscan` | sí | 45 s |

#### A reputación [VirusTotal]

Detecciones, reputación y categorías.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `virustotal` | Dominio, Nombre DNS, Dirección IP, URL, Hash | propiedades de la entidad de entrada | VirusTotal | `virustotal` | sí | 45 s |

#### A servicios y banners [Shodan]

Informe completo de Shodan: servicios, productos, SO, hosts y CVEs.

| Id | Entrada | Salida | Fuentes | Clave API | En «Ejecutar todos» | Tiempo máximo |
|---|---|---|---|---|---|---|
| `shodan_host` | Dirección IP | Nombre DNS, Dominio, Vulnerabilidad, Organización | Shodan | `shodan` | sí | 45 s |

## Máquinas

Las máquinas encadenan transforms. La etapa 1 se ejecuta sobre las entidades seleccionadas; cada etapa siguiente sólo sobre lo que produjo la anterior (un transform sólo se ejecuta si el tipo de entrada encaja). Toda la ejecución está limitada por *Ajustes → General → Máximo de entidades por máquina*.

### Huella de dominio (`domain_footprint`)

DNS, registro, subdominios y web; luego resuelve cada host y perfila cada IP.

*Pensada para:* Dominio

1. **Etapa 1:** A dirección IP [DNS], A servidores de correo [MX], A servidores de nombres [NS], A TXT / SPF / DMARC, A datos de registro [RDAP/WHOIS], A subdominios [Certificate Transparency], A sitio web, A contactos de seguridad [security.txt], A historial archivado [Wayback Machine]
2. **Etapa 2:** A dirección IP [DNS], A ubicación e ISP [GeoIP], A puertos, hosts y CVEs [InternetDB], A nombre DNS [PTR], A entidades de la página, A dominio padre
3. **Etapa 3:** A ubicación e ISP [GeoIP], A puertos, hosts y CVEs [InternetDB], A bloque de red y AS [RIPEstat]

### Huella de IP (`ip_footprint`)

Titular, red, ubicación, servicios expuestos y nombres alojados en una IP.

*Pensada para:* Dirección IP, Bloque de red

1. **Etapa 1:** A nombre DNS [PTR], A bloque de red y titular [RDAP], A ubicación e ISP [GeoIP], A puertos, hosts y CVEs [InternetDB], A dominios en la misma IP, A bloque de red y AS [RIPEstat]
2. **Etapa 2:** A dominio padre, A dirección IP [DNS], A bloques anunciados y titular

### Huella de identidad (`identity_footprint`)

De un alias, correo, teléfono o nombre a cuentas, perfiles, filtraciones y nuevos alias, a dos niveles.

*Pensada para:* Alias, Correo, Teléfono, Persona

1. **Etapa 1:** A cuentas [barrido de sitios], A perfiles detallados, A perfil de GitHub y correos de commits, A alias (parte local), A dominio, A perfil de Gravatar, A filtraciones [XposedOrNot], A filtraciones [Have I Been Pwned], A operador, región y tipo de línea, A menciones web [buscador]
2. **Etapa 2:** A cuentas [barrido de sitios], A perfiles detallados, A perfil de GitHub y correos de commits, A perfil de Gravatar, A filtraciones [XposedOrNot], A filtraciones [Have I Been Pwned], A alias (parte local), A alias, A coordenadas / dirección [OSM]
3. **Etapa 3:** A perfiles detallados, A perfil de GitHub y correos de commits, A perfil de Gravatar, A coordenadas / dirección [OSM]

### Huella de sitio web (`web_footprint`)

Extrae contactos, perfiles y rastreadores de una web y sigue un paso los dominios enlazados.

*Pensada para:* URL, Dominio, Nombre DNS

1. **Etapa 1:** A sitio web, A entidades de la página, A nombre DNS / dominio, A historial archivado [Wayback Machine]
2. **Etapa 2:** A entidades de la página, A alias, A datos de registro [RDAP/WHOIS], A dirección IP [DNS]
3. **Etapa 3:** A perfiles detallados, A ubicación e ISP [GeoIP]

### Laberinto (expansión automática) (`labyrinth`)

Ejecuta todos los transforms por defecto sobre las semillas y sigue avanzando N niveles. Limitado por el ajuste «máximo de entidades por máquina».

*Pensada para:* cualquier entidad

Ejecuta todos los transforms **por defecto** sobre las semillas y vuelve a hacerlo sobre lo que producen, durante los niveles que elijas (1-4).

## Claves API

Todas son opcionales y se configuran en *Ajustes → Claves API*. Se guardan en `settings.json`, dentro de la carpeta de datos.

| Clave | Servicio | La usan |
|---|---|---|
| `shodan` | [Shodan](https://account.shodan.io/) | A servicios y banners [Shodan] |
| `virustotal` | [VirusTotal](https://www.virustotal.com/gui/my-apikey) | A reputación [VirusTotal] |
| `hunter` | [Hunter.io](https://hunter.io/api-keys) | A correos y personas [Hunter.io] |
| `hibp` | [Have I Been Pwned](https://haveibeenpwned.com/API/Key) | A filtraciones [Have I Been Pwned] |
| `abuseipdb` | [AbuseIPDB](https://www.abuseipdb.com/account/api) | A denuncias de abuso [AbuseIPDB] |
| `urlscan` | [URLScan.io](https://urlscan.io/user/profile/) | A páginas escaneadas [urlscan.io] |
| `github` | [GitHub token (60 -> 5000 req/h)](https://github.com/settings/tokens) | A perfil de GitHub y correos de commits |
| `serper` | [Serper.dev (Google search)](https://serper.dev/api-key) | A menciones web [buscador] |
| `brave` | [Brave Search API](https://api-dashboard.search.brave.com/app/keys) | A menciones web [buscador] |
