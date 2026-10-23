"""Transforms against mocked HTTP responses (no network needed)."""

import asyncio
import hashlib

import httpx

from daedalus.transforms import MACHINES, REGISTRY
from daedalus.transforms import dns as dns_mod
from daedalus.transforms import social as social_mod

from .conftest import run_transform, values


def test_registry_is_consistent():
    for t in REGISTRY.values():
        assert t.inputs, t.name
        assert t.title["en"] and t.title["es"], t.name
        assert t.description["en"] and t.description["es"], t.name
    for m in MACHINES.values():
        for stage in m.steps:
            for name in stage:
                assert name in REGISTRY, (m.name, name)


def test_crtsh_subdomains(engine_env, router):
    router.add(r"crt\.sh", json_body=[
        {"name_value": "www.example.com\nmail.example.com", "not_before": "2020-01-02T00:00:00"},
        {"name_value": "*.dev.example.com", "not_before": "2021-05-01T00:00:00"},
        {"name_value": "example.com", "not_before": "2019-01-01T00:00:00"},
        {"name_value": "evil.com", "not_before": "2019-01-01T00:00:00"},
    ])
    g, run, _ = run_transform(engine_env, router, "crtsh_subdomains", "domain", "example.com")
    assert run["status"] == "ok"
    assert values(g, "hostname") == ["dev.example.com", "mail.example.com", "www.example.com"]
    assert {ln["label"] for ln in g["links"]} == {"subdomain"}


def test_crtsh_falls_back_to_certspotter(engine_env, router):
    router.add(r"crt\.sh", status=502, text="bad gateway")
    router.add(r"certspotter", json_body=[{"dns_names": ["a.example.com", "example.com"], "not_before": "2022-01-01"}])
    g, run, _ = run_transform(engine_env, router, "crtsh_subdomains", "domain", "example.com")
    assert values(g, "hostname") == ["a.example.com"]


def test_result_limit_truncates(engine_env, router):
    router.add(r"crt\.sh", json_body=[{"name_value": f"h{i}.example.com"} for i in range(30)])
    g, run, _ = run_transform(engine_env, router, "crtsh_subdomains", "domain", "example.com", limit=12)
    assert len(values(g, "hostname")) == 12
    assert "limit reached" in run["message"]


def test_internetdb(engine_env, router):
    router.add(r"internetdb\.shodan\.io/1\.2\.3\.4", json_body={
        "ip": "1.2.3.4", "ports": [22, 443], "cpes": ["cpe:/a:openbsd:openssh"], "tags": ["vpn"],
        "hostnames": ["vpn.example.com"], "vulns": ["CVE-2023-38408"]})
    g, run, _ = run_transform(engine_env, router, "shodan_internetdb", "ip", "1.2.3.4")
    ip = next(e for e in g["entities"] if e["type"] == "ip")
    assert ip["props"]["open_ports"] == [22, 443]
    assert values(g, "hostname") == ["vpn.example.com"]
    assert values(g, "vulnerability") == ["CVE-2023-38408"]


def test_rdap_domain(engine_env, router):
    router.add(r"rdap\.org/domain/example\.com", json_body={
        "events": [{"eventAction": "registration", "eventDate": "2001-02-03T00:00:00Z"},
                   {"eventAction": "expiration", "eventDate": "2030-02-03T00:00:00Z"}],
        "status": ["active"],
        "nameservers": [{"ldhName": "NS1.EXAMPLE.NET"}],
        "entities": [
            {"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Good Registrar Inc"]]],
             "entities": [{"roles": ["abuse"], "vcardArray": ["vcard", [["email", {}, "text", "abuse@registrar.test"]]]}]},
            {"roles": ["registrant"], "vcardArray": ["vcard", [
                ["fn", {}, "text", "Jane Roe"], ["org", {}, "text", "Roe Industries"],
                ["email", {}, "text", "jane@roe.test"]]]},
            {"roles": ["technical"], "vcardArray": ["vcard", [["fn", {}, "text", "REDACTED FOR PRIVACY"]]]},
        ]})
    g, run, _ = run_transform(engine_env, router, "rdap_domain", "domain", "example.com")
    assert run["status"] == "ok"
    assert values(g, "organization") == ["Good Registrar Inc", "Roe Industries"]
    assert values(g, "person") == ["Jane Roe"]
    assert values(g, "email") == ["jane@roe.test"]  # registrar abuse desk is ignored
    assert values(g, "hostname") == ["ns1.example.net"]
    dom = next(e for e in g["entities"] if e["type"] == "domain")
    assert dom["props"]["registered"] == "2001-02-03"
    assert ["Domain registered", "2001-02-03"] in dom["props"]["_dates"]


def test_ip_geolocation(engine_env, router):
    router.add(r"ipwho\.is/8\.8\.8\.8", json_body={
        "success": True, "country": "United States", "country_code": "US", "region": "California",
        "city": "Mountain View", "latitude": 37.4, "longitude": -122.1,
        "connection": {"asn": 15169, "org": "Google LLC", "isp": "Google LLC"}, "timezone": {"id": "America/Los_Angeles"}})
    g, _, _ = run_transform(engine_env, router, "ip_geolocation", "ip", "8.8.8.8")
    loc = next(e for e in g["entities"] if e["type"] == "location")
    assert loc["value"] == "Mountain View, California, United States" and loc["props"]["_lat"] == 37.4
    assert values(g, "asn") == ["AS15169"]
    assert values(g, "organization") == ["Google LLC"]


def test_gravatar_legacy_profile(engine_env, router):
    md5 = hashlib.md5(b"jane@roe.test").hexdigest()  # noqa: S324
    router.add(rf"gravatar\.com/{md5}\.json", json_body={"entry": [{
        "profileUrl": "https://gravatar.com/janeroe", "preferredUsername": "janeroe", "displayName": "Jane Roe",
        "currentLocation": "Lisbon, Portugal", "thumbnailUrl": "https://0.gravatar.com/avatar/x",
        "accounts": [{"shortname": "github", "url": "https://github.com/janeroe", "username": "janeroe"}],
        "urls": [{"value": "https://roe.test"}]}]})
    g, run, _ = run_transform(engine_env, router, "gravatar", "email", "jane@roe.test")
    assert run["status"] == "ok"
    assert values(g, "person") == ["Jane Roe"]
    assert values(g, "location") == ["Lisbon, Portugal"]
    assert "https://github.com/janeroe" in values(g, "account")
    assert values(g, "url") == ["https://roe.test/"]


def test_xposedornot(engine_env, router):
    router.add(r"xposedornot\.com/v1/breach-analytics", json_body={"ExposedBreaches": {"breaches_details": [
        {"breach": "Adobe", "domain": "adobe.com", "xposed_date": "2013", "xposed_records": 152445165,
         "xposed_data": "Email addresses;Password hints"}]}})
    g, _, _ = run_transform(engine_env, router, "xposedornot", "email", "a@b.test")
    br = next(e for e in g["entities"] if e["type"] == "breach")
    assert br["value"] == "Adobe" and br["props"]["data_classes"] == ["Email addresses", "Password hints"]


def test_github_profile_and_commit_emails(engine_env, router):
    router.add(r"api\.github\.com/users/octo/events", json_body=[
        {"payload": {"commits": [{"author": {"email": "octo@corp.test", "name": "Octo Cat"}},
                                 {"author": {"email": "1+octo@users.noreply.github.com", "name": "x"}}]}}])
    router.add(r"api\.github\.com/users/octo$", json_body={
        "login": "octo", "html_url": "https://github.com/octo", "name": "Octo Cat", "company": "@acme",
        "location": "Berlin", "blog": "octo.dev", "twitter_username": "octo_x", "created_at": "2011-01-25T18:44:36Z",
        "followers": 10, "public_repos": 3})
    g, run, _ = run_transform(engine_env, router, "github_profile", "username", "octo")
    assert run["status"] == "ok", run["message"]
    assert values(g, "email") == ["octo@corp.test"]
    assert values(g, "organization") == ["acme"]
    assert values(g, "location") == ["Berlin"]
    assert values(g, "url") == ["https://octo.dev/"]
    assert "https://x.com/octo_x" in values(g, "account")
    acc = next(e for e in g["entities"] if e["value"] == "https://github.com/octo")
    assert acc["props"]["created"] == "2011-01-25"


def test_username_sweep_with_control_check(engine_env, router, monkeypatch):
    sites = {
        "Good": {"url": "https://good.test/{}", "errorType": "status_code"},
        "Liar": {"url": "https://liar.test/{}", "errorType": "status_code"},
        "Msg": {"url": "https://msg.test/u/{}", "errorType": "message", "errorMsg": "No such user"},
        "Waf": {"url": "https://waf.test/{}", "errorType": "status_code"},
    }

    async def fake_sites(ctx):
        return sites

    monkeypatch.setattr(social_mod, "load_sites", fake_sites)
    router.add(r"good\.test/teo$", text="profile")
    router.add(r"liar\.test/", text="always yes")  # answers 200 for any alias -> discarded
    router.add(r"msg\.test/u/teo$", text="hello teo")
    router.add(r"msg\.test/u/", text="No such user")
    router.add(r"waf\.test/", status=403, text="Just a moment...")
    g, run, _ = run_transform(engine_env, router, "username_sweep", "username", "teo")
    assert values(g, "account") == ["https://good.test/teo", "https://msg.test/u/teo"]
    user = next(e for e in g["entities"] if e["type"] == "username")
    assert user["props"]["_unverified"] == [["Waf", "https://waf.test/teo"]]


def test_builtin_sites_are_well_formed():
    sites = social_mod.builtin_sites()
    assert len(sites) >= 70
    for name, s in sites.items():
        assert "{}" in s["url"], name
        assert s["errorType"] in ("status_code", "message", "response_url"), name
        if s["errorType"] == "message":
            assert s.get("errorMsg"), name


def test_web_page_scan(engine_env, router):
    html = """<html><head><title>Acme Labs</title><meta name="description" content="We build mazes">
      <script async src="https://www.googletagmanager.com/gtag/js?id=G-ABCD123456"></script></head>
      <body><a href="mailto:press@acme.test">press</a> Contact: jane@acme.test or +34 612 345 678
      <a href="https://x.com/acmelabs">X</a> <a href="https://github.com/acme-labs">code</a>
      <a href="https://partner.test/page">partner</a> <a href="https://www.google.com/">g</a></body></html>"""
    router.add(r"acme\.test/", text=html, headers={"content-type": "text/html", "server": "nginx"})
    g, run, _ = run_transform(engine_env, router, "web_page_scan", "url", "https://acme.test/")
    assert run["status"] == "ok", run["message"]
    assert values(g, "email") == ["jane@acme.test", "press@acme.test"]
    assert values(g, "tracking_code") == ["G-ABCD123456"]
    assert set(values(g, "account")) == {"https://x.com/acmelabs", "https://github.com/acme-labs"}
    assert values(g, "domain") == ["partner.test"]
    assert values(g, "phone") == ["+34612345678"]
    page = next(e for e in g["entities"] if e["type"] == "url")
    assert page["props"]["title"] == "Acme Labs" and "server: nginx" in page["props"]["technologies"]


def test_ssrf_guard_blocks_private_targets(engine_env, router):
    _store, settings, _ = engine_env
    settings.update({"block_private_targets": True})
    router.add(r"127\.0\.0\.1", text="secret")
    g, run, _ = run_transform(engine_env, router, "web_page_scan", "url", "http://127.0.0.1:8080/admin")
    assert run["status"] == "skipped" and "private" in run["message"]
    assert not [c for c in router.calls if "127.0.0.1" in c]


def test_web_search_duckduckgo(engine_env, router):
    html = """<div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a"
      href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fforum.test%2Fu%2Fteo&amp;rut=abc">Teo on <b>Forum</b></a></h2>
      <a class="result__snippet" href="#">profile of teo</a></div>
      <div class="result"><a class="result__a" href="https://blog.test/post">Blog</a></div>"""
    router.add(r"POST https://html\.duckduckgo\.com/html/", text=html)
    g, run, _ = run_transform(engine_env, router, "web_search", "username", "teo")
    assert values(g, "url") == ["https://blog.test/post", "https://forum.test/u/teo"]
    hit = next(e for e in g["entities"] if e["value"] == "https://forum.test/u/teo")
    assert hit["props"]["title"] == "Teo on Forum" and hit["props"]["snippet"] == "profile of teo"


def test_wallet_info_btc(engine_env, router):
    addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    router.add(rf"blockstream\.info/api/address/{addr}/txs", json_body=[{"status": {"block_time": 1696032000}}])
    router.add(rf"blockstream\.info/api/address/{addr}$", json_body={
        "chain_stats": {"funded_txo_sum": 150000000, "spent_txo_sum": 50000000, "tx_count": 4}})
    g, run, _ = run_transform(engine_env, router, "wallet_info", "crypto", addr)
    w = g["entities"][0]
    assert w["props"]["balance"] == "1.00000000 BTC" and w["props"]["tx_count"] == 4
    assert w["props"]["last_activity"] == "2023-09-30"


def test_phone_info_offline(engine_env, router):
    g, run, _ = run_transform(engine_env, router, "phone_info", "phone", "+34612345678")
    p = next(e for e in g["entities"] if e["type"] == "phone")
    assert p["props"]["valid"] is True and p["props"]["country"] == "Spain" and p["props"]["line_type"] == "mobile"
    assert values(g, "location") == ["Spain"]


def test_email_to_domain_skips_free_providers(engine_env, router):
    g, run, _ = run_transform(engine_env, router, "email_to_domain", "email", "someone@gmail.com")
    assert values(g, "domain") == []
    assert g["entities"][0]["props"]["free_provider"] is True
    g, _, _ = run_transform(engine_env, router, "email_to_domain", "email", "jane@roe.test")
    assert values(g, "domain") == ["roe.test"]


def test_dns_txt_spf_and_dmarc(engine_env, router, monkeypatch):
    async def fake_resolve(name, rtype):
        return {
            ("example.com", "TXT"): ['v=spf1 include:_spf.google.com ip4:192.0.2.0/24 -all',
                                     "google-site-verification=abc123"],
            ("_dmarc.example.com", "TXT"): ["v=DMARC1; p=reject; rua=mailto:dmarc@example.com"],
        }.get((name, rtype), [])

    monkeypatch.setattr(dns_mod, "resolve", fake_resolve)
    g, run, _ = run_transform(engine_env, router, "dns_txt", "domain", "example.com")
    assert values(g, "hostname") == ["_spf.google.com"]
    assert values(g, "netblock") == ["192.0.2.0/24"]
    assert values(g, "email") == ["dmarc@example.com"]
    d = next(e for e in g["entities"] if e["type"] == "domain")
    assert d["props"]["dmarc_policy"] == "reject"
    assert d["props"]["verification_tokens"] == ["google-site-verification=abc123"]


def test_missing_key_is_skipped(engine_env, router):
    _, run, _ = run_transform(engine_env, router, "shodan_host", "ip", "1.2.3.4")
    assert run["status"] == "skipped" and "Shodan" in run["message"]


def test_network_errors_are_reported(engine_env, router):
    def boom(request):
        raise httpx.ConnectError("down", request=request)

    router.add(r"internetdb", boom)
    _, run, _ = run_transform(engine_env, router, "shodan_internetdb", "ip", "1.2.3.4")
    assert run["status"] == "error" and "ConnectError" in run["message"]


def test_machine_chains_stages(engine_env, router, monkeypatch):
    """identity machine: email -> alias (stage 1) -> GitHub profile of that alias (stage 2)."""
    store, settings, make = engine_env
    router.add(r"api\.github\.com/users/teolabrys$", json_body={"login": "teolabrys", "html_url": "https://github.com/teolabrys",
                                                               "name": "Teo Labrys"})

    async def no_sites(ctx):
        return {}

    monkeypatch.setattr(social_mod, "load_sites", no_sites)

    async def go():
        eng = await make(router)
        case = store.create_case("m")
        ent, _ = store.upsert_entity(case["id"], "email", "teolabrys@example.test", root=True)
        job = eng.run_machine(case["id"], [ent["id"]], "identity_footprint")
        await job.task
        await eng.stop()
        return case["id"], job

    case_id, job = asyncio.run(go())
    g = store.graph(case_id)
    assert "username:teolabrys" in {e["id"] for e in g["entities"]}
    assert "https://github.com/teolabrys" in values(g, "account")
    assert values(g, "person") == ["Teo Labrys"]
    assert job.events[-1]["type"] == "done"
    assert [ev["index"] for ev in job.events if ev["type"] == "stage"][:2] == [0, 1]


def test_job_cancel(engine_env, router):
    store, _, make = engine_env

    async def go():
        eng = await make(router)
        router.add(r"internetdb", lambda req: httpx.Response(200, json={}))
        case = store.create_case("c")
        ent, _ = store.upsert_entity(case["id"], "ip", "1.2.3.4")
        job = eng.run_transforms(case["id"], [ent["id"]], None)
        await asyncio.sleep(0)
        job.cancel()
        try:
            await job.task
        except asyncio.CancelledError:
            pass
        await eng.stop()
        return job

    job = asyncio.run(go())
    assert job.done and job.events[-1]["type"] == "done"



def test_plugin_loader(tmp_path):
    from pathlib import Path

    from daedalus.transforms import load_plugins

    folder = tmp_path / "plugins"
    folder.mkdir()
    src = Path(__file__).resolve().parent.parent / "examples" / "plugins" / "email_hashes.py"
    (folder / "email_hashes.py").write_text(src.read_text())
    (folder / "broken.py").write_text("raise RuntimeError('boom')")
    try:
        assert load_plugins(folder) == ["plugin_email_hashes"]
        assert load_plugins(folder) == []  # idempotent
    finally:
        REGISTRY.pop("plugin_email_hashes", None)
