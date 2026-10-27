# Contributing to DAEDALUS

Thanks for your interest in DAEDALUS. Bug reports, new transforms, translations, documentation and fixes are all
welcome. Issues and pull requests can be written in English or Spanish.

- [Before you start](#before-you-start)
- [Development setup](#development-setup)
- [Adding a transform or machine](#adding-a-transform-or-machine)
- [Front-end changes](#front-end-changes)
- [Pull requests](#pull-requests)
- [Reporting security issues](#reporting-security-issues)
- [Licence of contributions](#licence-of-contributions)

## Before you start

- **Small fixes**, such as typos, obvious bugs or a missing translation, can go straight to a pull request.
- **Larger changes**, such as a new view, a new dependency or a change to the data model or HTTP API, should start
  with an issue that describes the problem and the approach. Agreeing on the approach first avoids wasted work.
- **Scope.** DAEDALUS collects what public sources and services the analyst configures return. Contributions that
  bypass authentication, rate limits or access controls, that scrape against a site's terms, or that exist mainly
  to track private individuals will not be merged. See the [Ethics](README.md#ethics) section.

## Development setup

You need Python 3.11 or newer.

```bash
git clone https://github.com/BreaGG/DAEDALUS.git
cd DAEDALUS
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m daedalus                               # http://127.0.0.1:8787 (see --help)
```

Before you push, run the same checks as CI (GitHub Actions, Python 3.11 to 3.13):

```bash
ruff check daedalus tests
pytest -q
python scripts/gen_docs.py --check
```

The test suite must not touch the network. Every HTTP call goes through the `router` fixture in
[`tests/conftest.py`](tests/conftest.py), which serves mocked responses.

To try the interface with data, import [`examples/operation-minotaur.json`](examples/operation-minotaur.json), a
fictional investigation, with **Import** in the top bar.

## Adding a transform or machine

The [technical documentation](docs/en/technical.md#10-extending-daedalus) describes the `Transform` class, the
`Context` API and machines in full. In short:

1. Add the class to the module of its family in [`daedalus/transforms/`](daedalus/transforms/), such as `dns.py`,
   `web.py` or `social.py`, and decorate it with `@register`.
2. Give it a unique `name` and bilingual texts: `title = L("English", "Español")`, and the same for `description`.
3. Keep it asynchronous. Use `ctx.http` or `ctx.get_json`, and wrap any blocking library in `asyncio.to_thread`.
4. Call `await ctx.assert_public(url)` before fetching a URL that comes from user data. This is the SSRF guard.
5. Declare API keys in `keys` (required) or `optional_keys`, and add new key names to `API_KEYS` in
   [`daedalus/config.py`](daedalus/config.py). A transform without its key is skipped, never broken.
6. Use `raise Skip("reason")` for expected failures, such as no key, an unsupported input or a non-200 response.
   Unexpected exceptions are reported as errors.
7. Add a test with mocked HTTP:

   ```python
   def test_my_transform(engine_env, router):
       router.add(r"api\.example\.org", json_body={"accounts": ["https://example.org/alice"]})
       g, run, _ = run_transform(engine_env, router, "my_transform", "username", "alice")
       assert run["status"] == "ok"
       assert values(g, "account") == ["https://example.org/alice"]
   ```

8. Regenerate the reference with `python scripts/gen_docs.py`. This rewrites `docs/en/transforms.md` and
   `docs/es/transforms.md`, and a test fails if they are out of date.

If a transform only makes sense for your own setup, ship it as a plugin in the data folder instead. See
[`examples/plugins/email_hashes.py`](examples/plugins/email_hashes.py).

## Front-end changes

The interface is plain HTML, CSS and ES modules in [`daedalus/web/`](daedalus/web/). It has no build step and no
framework, and it loads nothing from a CDN, so it works offline. Libraries live in `daedalus/web/vendor/` and are
listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

- **Translations.** Every visible string goes through `t("key")`, or through the `data-i18n`, `data-i18n-ph` and
  `data-i18n-title` attributes. Add each new key to both `DICT.en` and `DICT.es` in
  [`js/i18n.js`](daedalus/web/js/i18n.js).
- **Icons.** Use `uiIcon(name)` for interface glyphs and `iconSvg(type)` for entity types, both from
  [`js/icons.js`](daedalus/web/js/icons.js). In static HTML, write `<i data-ico="name"></i>`. Do not use emoji or
  Unicode symbols as icons.
- **Style.** Keep the existing look: flat surfaces, 1px borders, 2 to 4px corners, gold as an accent and never as a
  gradient fill. Use the colour tokens defined in `:root` of [`css/daedalus.css`](daedalus/web/css/daedalus.css)
  rather than new hard-coded colours.
- **Screenshots.** Include before and after screenshots in the pull request for any visible change. If it changes
  something shown in `docs/img/`, update those images too.

## Pull requests

- Branch from `main` and keep each pull request to one topic.
- Write commit messages in the imperative, such as "Add Keybase transform" or "Fix map popup overflow".
- Update the user guide or the technical documentation, in both `docs/en/` and `docs/es/`, when behaviour changes.
- Checklist before you request a review:
  - [ ] `ruff check daedalus tests` and `pytest -q` pass
  - [ ] New behaviour has tests, and no test touches the network
  - [ ] New strings are translated into English and Spanish
  - [ ] `python scripts/gen_docs.py` was run if transforms or machines changed
  - [ ] Screenshots are attached for UI changes

## Reporting security issues

Do not open a public issue for a vulnerability, such as an SSRF bypass, path traversal or code execution. Report it
privately through GitHub's
[security advisory form](https://github.com/BreaGG/DAEDALUS/security/advisories/new) with steps to reproduce it. You
will get an answer before any details are made public.

## Licence of contributions

DAEDALUS is licensed under the [GNU General Public License v3.0 or later](LICENSE). By submitting a contribution,
you agree that it is licensed under the same terms, and you confirm that you have the right to submit it. Do not
add code or data copied from projects whose licence is incompatible with GPL-3.0-or-later. When you bundle a
third-party library, record its licence in `THIRD_PARTY_NOTICES.md`.
