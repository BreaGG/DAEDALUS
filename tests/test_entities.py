import pytest

from daedalus.entities import detect_type, display_label, entity_id, latlon, normalize, registered_domain


@pytest.mark.parametrize("value,expected", [
    ("john@example.com", "email"),
    ("8.8.8.8", "ip"),
    ("2001:db8::1", "ip"),
    ("10.0.0.0/8", "netblock"),
    ("example.com", "domain"),
    ("example.co.uk", "domain"),
    ("mail.example.com", "hostname"),
    ("john.doe", "username"),
    ("teolabrys", "username"),
    ("@teolabrys", "username"),
    ("John Smith", "person"),
    ("+34 612 345 678", "phone"),
    ("https://x.com/someone", "url"),
    ("AS15169", "asn"),
    ("CVE-2021-44228", "vulnerability"),
    ("G-ABCDEF1234", "tracking_code"),
    ("UA-12345678-1", "tracking_code"),
    ("d41d8cd98f00b204e9800998ecf8427e", "hash"),
    ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "crypto"),
    ("0x52908400098527886E0F7030069857D2E4169EE7", "crypto"),
    ("40.4168, -3.7038", "location"),
    ("selling access to a corporate vpn", "phrase"),
])
def test_detect_type(value, expected):
    assert detect_type(value) == expected


def test_normalize():
    assert normalize("domain", "Example.COM.") == "example.com"
    assert normalize("hostname", "*.Dev.Example.com") == "dev.example.com"
    assert normalize("email", " John@Example.com ") == "john@example.com"
    assert normalize("username", "@TeoLabrys") == "teolabrys"
    assert normalize("phone", "+34 (612) 345-678") == "+34612345678"
    assert normalize("asn", "as 15169") == "AS15169"
    assert normalize("ip", "2001:0db8:0000::1") == "2001:db8::1"
    assert normalize("netblock", "10.1.2.3/8") == "10.0.0.0/8"
    assert normalize("url", "https://example.com") == "https://example.com/"
    assert normalize("person", "  John   Smith ") == "John Smith"


def test_entity_id_is_case_insensitive_for_free_text():
    assert entity_id("person", "John Smith") == entity_id("person", "john smith")
    assert entity_id("domain", "example.com") == "domain:example.com"


def test_registered_domain():
    assert registered_domain("a.b.example.com") == "example.com"
    assert registered_domain("shop.example.co.uk") == "example.co.uk"
    assert registered_domain("user.github.io") == "user.github.io"
    assert registered_domain("example.com") == "example.com"


def test_display_label_and_latlon():
    assert display_label("account", "https://x.com/a", {"platform": "X", "username": "a"}) == "X · a"
    assert display_label("asn", "AS1", {"name": "NET"}) == "AS1 · NET"
    assert latlon("40.4, -3.7") == (40.4, -3.7)
    assert latlon("95, 10") is None
