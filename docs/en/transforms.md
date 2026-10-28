# Entity, transform and machine reference

Author: **Alejandro Brea**

> Generated from the source code by `scripts/gen_docs.py`. Do not edit by hand.

[Entities](#entities) · [Transforms](#transforms) · [Machines](#machines) · [API keys](#api-keys)

## Entities

Every node in the graph is an entity of one of these types. Types with an example can be typed in the quick-add bar and are recognised automatically; the others are created from the palette or by transforms.

| Type | Id | Category | Create by hand | Auto-detected from |
|---|---|---|---|---|
| Person | `person` | Identity | yes | `John Smith` |
| Alias | `username` | Identity | yes | `teolabrys` |
| Email address | `email` | Identity | yes | `daedalusintelligence@gmail.com` |
| Phone number | `phone` | Identity | yes | `+34 612 345 678` |
| Online account | `account` | Identity | yes | palette / menu only |
| Organization | `organization` | Identity | yes | palette / menu only |
| Domain | `domain` | Infrastructure | yes | `example.com` |
| DNS name | `hostname` | Infrastructure | yes | `mail.example.com` |
| IP address | `ip` | Infrastructure | yes | `203.0.113.17` |
| Netblock | `netblock` | Infrastructure | yes | `203.0.113.0/24` |
| AS number | `asn` | Infrastructure | yes | `AS64500` |
| URL | `url` | Web | yes | `https://example.com/about` |
| Tracking code | `tracking_code` | Web | yes | `G-ABCD123456` |
| Location | `location` | Location | yes | `40.4168, -3.7038` |
| Crypto wallet | `crypto` | Crypto & finance | yes | `bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4` |
| Hash | `hash` | Artifacts | yes | `d41d8cd98f00b204e9800998ecf8427e` |
| Image | `image` | Artifacts | no | created by uploading a photo |
| Phrase | `phrase` | Artifacts | yes | `selling access to a vpn` |
| Data breach | `breach` | Threat intel | no | created by breach transforms |
| Vulnerability | `vulnerability` | Threat intel | yes | `CVE-2021-44228` |

## Transforms

Transforms take one entity and return related entities and/or new properties. Right-click an entity (or a selection) to run them. *Run all* runs every transform marked **default**.

**46** transforms in 9 categories, 41 of them need no API key.

### DNS

#### To DNS name [PTR]

Reverse DNS lookup.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `reverse_dns` | IP address | DNS name | DNS | none | yes | 45 s |

#### To DNS names and IPs [HackerTarget]

Passive host search (free tier: 50 queries/day).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `hackertarget_hosts` | Domain | DNS name, IP address | HackerTarget | none | — | 45 s |

#### To domains on the same IP

Reverse IP lookup (HackerTarget free tier).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `reverse_ip` | IP address | DNS name | HackerTarget | none | yes | 45 s |

#### To IP address [DNS]

Resolve A and AAAA records.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `dns_resolve` | Domain, DNS name | IP address | DNS | none | yes | 45 s |

#### To mail servers [MX]

MX records of the domain.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `dns_mx` | Domain | DNS name | DNS | none | yes | 45 s |

#### To name servers [NS]

NS records of the domain.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `dns_ns` | Domain | DNS name | DNS | none | yes | 45 s |

#### To parent domain

Registrable domain of a DNS name.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `hostname_to_domain` | DNS name | Domain | — | none | yes | 45 s |

#### To subdomains [Certificate Transparency]

Names found in TLS certificates (crt.sh, CertSpotter fallback).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `crtsh_subdomains` | Domain | DNS name | crt.sh, CertSpotter | none | yes | 90 s |

#### To TXT / SPF / DMARC

Reads TXT records: SPF includes become domains and IPs, DMARC report addresses become emails, and third-party verification tokens are stored as properties.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `dns_txt` | Domain | Domain, DNS name, IP address, Netblock, Email address | DNS | none | yes | 45 s |

### Infrastructure

#### To announced netblocks and owner

Holder of an autonomous system and the prefixes it announces.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `asn_prefixes` | AS number | Netblock, Organization | RIPEstat | none | yes | 45 s |

#### To location and ISP [GeoIP]

Approximate geolocation, ISP and autonomous system.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `ip_geolocation` | IP address | Location, AS number, Organization | ipwho.is, ip-api.com | none | yes | 45 s |

#### To netblock and AS [RIPEstat]

Announced prefix and origin AS of an IP, or the origin AS of a netblock.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `ripestat_network` | IP address, Netblock | Netblock, AS number | RIPEstat | none | yes | 45 s |

#### To netblock and owner [RDAP]

Network allocation, owner organisation and abuse contact.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `rdap_ip` | IP address | Netblock, Organization, Email address | RDAP | none | yes | 45 s |

#### To ports, hostnames and CVEs [InternetDB]

Shodan's free InternetDB: open ports, CPEs, tags, hostnames and known vulnerabilities.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `shodan_internetdb` | IP address | DNS name, Vulnerability | Shodan InternetDB | none | yes | 45 s |

#### To registration data [RDAP/WHOIS]

Registrar, dates, contacts and name servers. Falls back to WHOIS when the TLD has no RDAP.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `rdap_domain` | Domain | Organization, Email address, Phone number, Person, DNS name, Location | RDAP, WHOIS | none | yes | 45 s |

### Web

#### To archive history [Wayback Machine]

First and last capture in the Internet Archive.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `wayback` | Domain, DNS name, URL | properties of the input entity | Internet Archive | none | yes | 45 s |

#### To archived files [Wayback Machine]

Archived URLs of the domain that look like documents, backups or config files.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `wayback_urls` | Domain | URL | Internet Archive | none | — | 90 s |

#### To DNS name / domain

Host part of a URL.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `url_to_host` | URL | Domain, DNS name, IP address | — | none | yes | 45 s |

#### To entities on the page

Downloads the page and extracts emails, phones, social profiles, tracking codes, technologies and the domains it links to.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `web_page_scan` | URL | Email address, Phone number, Online account, Tracking code, Domain | HTTP | none | yes | 45 s |

#### To security contacts [security.txt]

Contacts published in /.well-known/security.txt.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `security_txt` | Domain | Email address, URL | HTTP | none | yes | 45 s |

#### To website

Checks whether the name serves a website over HTTPS or HTTP.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `to_website` | Domain, DNS name | URL | HTTP | none | yes | 45 s |

### Identity

#### To alias (local part)

The part before the @, when it looks like a personal handle.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `email_to_alias` | Email address | Alias | — | none | yes | 45 s |

#### To carrier, region and line type

Offline analysis with libphonenumber: validity, country, carrier, line type and time zone.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `phone_info` | Phone number | Location | libphonenumber | none | yes | 45 s |

#### To domain

Domain of the address. Free webmail providers are noted but not added, so they do not become false bridges between unrelated people.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `email_to_domain` | Email address | Domain | — | none | yes | 45 s |

#### To emails and people [Hunter.io]

Addresses published for the domain, with names and positions.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `hunter_domain` | Domain | Email address, Person, Organization | Hunter.io | `hunter` | yes | 45 s |

#### To likely aliases (permutations)

Typical handles built from the name (jdoe, john.doe...). They are guesses: verify them with the account sweep.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `person_to_aliases` | Person | Alias | — | none | — | 45 s |

#### Validate address [MX]

Does the domain accept mail? Is it a disposable provider?

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `email_validate` | Email address | properties of the input entity | — | none | yes | 45 s |

### Social & accounts

#### To accounts [site sweep]

Checks the alias on ~75 sites (400+ with the Sherlock database enabled in settings). Every hit is double-checked against a random alias to discard sites that answer 'yes' to everything.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `username_sweep` | Alias | Online account | 75+ sites, Sherlock DB (optional) | none | yes | 180 s |

#### To alias

Handle used on the account.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `account_to_alias` | Online account | Alias | — | none | yes | 45 s |

#### To detailed profiles

Rich public profiles (name, bio, location, links, creation date) from GitLab, Keybase, Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram and X.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `username_profiles` | Alias | Online account, Person, Location, URL, Email address, Domain | GitLab, Keybase, Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram, X | none | yes | 90 s |

#### To GitHub profile and commit emails

Profile data plus the author emails leaked in public commits.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `github_profile` | Alias | Online account, Person, Organization, Location, URL, Email address | GitHub API | optional: `github` | yes | 60 s |

#### To Gravatar profile

Public Gravatar profile: name, location, avatar and verified accounts.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `gravatar` | Email address | Online account, Person, Location, URL | Gravatar | none | yes | 45 s |

### Search engines

#### To search dorks (links)

Ready-made Google / Bing / DuckDuckGo / Yandex queries attached to the entity for manual review.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `dork_links` | Person, Alias, Email address, Phone number, Domain, Organization, Phrase | properties of the input entity | — | none | — | 45 s |

#### To web mentions [search engine]

Pages that mention the value. Uses Serper (Google) or Brave when a key is set, otherwise DuckDuckGo.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `web_search` | Person, Alias, Email address, Phone number, Phrase, Organization, Tracking code, Crypto wallet, Hash, Domain | URL | Serper, Brave, DuckDuckGo | optional: `serper`, `brave` | yes | 45 s |

#### To Wikidata entries

Matching items in Wikidata (public figures, companies, places).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `wikidata` | Person, Organization, Location | URL | Wikidata | none | yes | 45 s |

### Location

#### To coordinates / address [OSM]

Places a location on the map (or names the place for raw coordinates).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `geocode` | Location | properties of the input entity | OpenStreetMap Nominatim | none | yes | 45 s |

### Blockchain

#### To balance and activity

Balance, transaction count and first/last activity (Bitcoin via Blockstream, Ethereum via Blockscout).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `wallet_info` | Crypto wallet | properties of the input entity | Blockstream, Blockscout | none | yes | 45 s |

#### To counterparty wallets

Addresses that sent to or received from this wallet in its most recent transactions.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `wallet_counterparties` | Crypto wallet | Crypto wallet | Blockstream, Blockscout | none | — | 45 s |

### Threat intel

#### To abuse reports [AbuseIPDB]

Abuse confidence score and reports in the last 90 days.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `abuseipdb` | IP address | properties of the input entity | AbuseIPDB | `abuseipdb` | yes | 45 s |

#### To CVE details [NVD]

Description, CVSS score and publication date.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `cve_info` | Vulnerability | properties of the input entity | NIST NVD | none | yes | 45 s |

#### To data breaches [Have I Been Pwned]

Breaches from HIBP (paid API key).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `hibp` | Email address | Data breach | Have I Been Pwned | `hibp` | yes | 45 s |

#### To data breaches [XposedOrNot]

Public breaches where the address appears (free, no key).

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `xposedornot` | Email address | Data breach | XposedOrNot | none | yes | 45 s |

#### To known file [CIRCL hashlookup]

Is the hash a known file (NSRL and other known-good sets)?

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `hash_lookup` | Hash | properties of the input entity | CIRCL hashlookup | none | yes | 45 s |

#### To reputation [VirusTotal]

Detection stats, reputation and categories.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `virustotal` | Domain, DNS name, IP address, URL, Hash | properties of the input entity | VirusTotal | `virustotal` | yes | 45 s |

#### To scanned pages [urlscan.io]

Public urlscan.io scans of the domain or IP: URLs, IPs and servers seen.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `urlscan` | Domain, DNS name, IP address | URL, IP address, Domain | urlscan.io | optional: `urlscan` | yes | 45 s |

#### To services and banners [Shodan]

Full Shodan host report: services, products, OS, hostnames and CVEs.

| Id | Input | Output | Sources | API key | In “Run all” | Timeout |
|---|---|---|---|---|---|---|
| `shodan_host` | IP address | DNS name, Domain, Vulnerability, Organization | Shodan | `shodan` | yes | 45 s |

## Machines

Machines chain transforms. Stage 1 runs on the selected entities; every following stage runs only on what the previous stage produced (a transform only runs where its input type matches). The whole run is capped by *Settings → General → Max entities per machine*.

### Domain footprint (`domain_footprint`)

DNS, registration, subdomains and website; then resolves every host and profiles each IP.

*Suggested for:* Domain

1. **Stage 1:** To IP address [DNS], To mail servers [MX], To name servers [NS], To TXT / SPF / DMARC, To registration data [RDAP/WHOIS], To subdomains [Certificate Transparency], To website, To security contacts [security.txt], To archive history [Wayback Machine]
2. **Stage 2:** To IP address [DNS], To location and ISP [GeoIP], To ports, hostnames and CVEs [InternetDB], To DNS name [PTR], To entities on the page, To parent domain
3. **Stage 3:** To location and ISP [GeoIP], To ports, hostnames and CVEs [InternetDB], To netblock and AS [RIPEstat]

### IP footprint (`ip_footprint`)

Owner, network, location, exposed services and co-hosted names of an IP address.

*Suggested for:* IP address, Netblock

1. **Stage 1:** To DNS name [PTR], To netblock and owner [RDAP], To location and ISP [GeoIP], To ports, hostnames and CVEs [InternetDB], To domains on the same IP, To netblock and AS [RIPEstat]
2. **Stage 2:** To parent domain, To IP address [DNS], To announced netblocks and owner

### Identity footprint (`identity_footprint`)

From an alias, email, phone or name to accounts, profiles, breaches and new aliases, two levels deep.

*Suggested for:* Alias, Email address, Phone number, Person

1. **Stage 1:** To accounts [site sweep], To detailed profiles, To GitHub profile and commit emails, To alias (local part), To domain, To Gravatar profile, To data breaches [XposedOrNot], To data breaches [Have I Been Pwned], To carrier, region and line type, To web mentions [search engine]
2. **Stage 2:** To accounts [site sweep], To detailed profiles, To GitHub profile and commit emails, To Gravatar profile, To data breaches [XposedOrNot], To data breaches [Have I Been Pwned], To alias (local part), To alias, To coordinates / address [OSM]
3. **Stage 3:** To detailed profiles, To GitHub profile and commit emails, To Gravatar profile, To coordinates / address [OSM]

### Website footprint (`web_footprint`)

Scrapes a site for contacts, profiles and trackers, then follows the linked domains one step.

*Suggested for:* URL, Domain, DNS name

1. **Stage 1:** To website, To entities on the page, To DNS name / domain, To archive history [Wayback Machine]
2. **Stage 2:** To entities on the page, To alias, To registration data [RDAP/WHOIS], To IP address [DNS]
3. **Stage 3:** To detailed profiles, To location and ISP [GeoIP]

### Labyrinth (auto-expand) (`labyrinth`)

Runs every default transform on the seeds and keeps walking outwards N levels. Bounded by the 'machine max entities' setting.

*Suggested for:* any entity

Runs every **default** transform on the seeds, then again on what they produced, for the number of levels you choose (1-4).

## API keys

All keys are optional and are set in *Settings → API keys*. They are stored in `settings.json` inside the data folder.

| Key | Service | Used by |
|---|---|---|
| `shodan` | [Shodan](https://account.shodan.io/) | To services and banners [Shodan] |
| `virustotal` | [VirusTotal](https://www.virustotal.com/gui/my-apikey) | To reputation [VirusTotal] |
| `hunter` | [Hunter.io](https://hunter.io/api-keys) | To emails and people [Hunter.io] |
| `hibp` | [Have I Been Pwned](https://haveibeenpwned.com/API/Key) | To data breaches [Have I Been Pwned] |
| `abuseipdb` | [AbuseIPDB](https://www.abuseipdb.com/account/api) | To abuse reports [AbuseIPDB] |
| `urlscan` | [URLScan.io](https://urlscan.io/user/profile/) | To scanned pages [urlscan.io] |
| `github` | [GitHub token (60 -> 5000 req/h)](https://github.com/settings/tokens) | To GitHub profile and commit emails |
| `serper` | [Serper.dev (Google search)](https://serper.dev/api-key) | To web mentions [search engine] |
| `brave` | [Brave Search API](https://api-dashboard.search.brave.com/app/keys) | To web mentions [search engine] |
