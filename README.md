# job-search-scraper-kit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-8A63D2.svg)](https://claude.com/claude-code)

A configurable job search tool — scrapes company ATS boards, LinkedIn and
regional job portals, filters by your own criteria, and scores/ranks the
results. Built as a combination of known public scraping approaches plus a
set of adaptations that turned out to matter in practice.

Buscador de empleo configurable — scrapea ATS de empresas, LinkedIn y
portales regionales, filtra por tus criterios y puntúa/ordena los
resultados. Es una combinación de enfoques de scraping ya conocidos más
adaptaciones propias que resultaron útiles en la práctica.

**Choose your language / Elegí tu idioma:**

- 🇬🇧 **[English →](./README.en.md)**
- 🇪🇸 **[Español →](./README.es.md)**

---

Quick facts:

- Config-driven — all search criteria live in one YAML file, no code edits needed
- `sources/ats.py` — Greenhouse / Ashby / Lever, stable public APIs
- `sources/linkedin.py` — LinkedIn's public guest jobs endpoint (disabled by default — see the ToS note in either README)
- `sources/regional.py` — GetOnBoard implemented; a few other LATAM portals left as documented stubs (they're JS-rendered SPAs and need a real browser, e.g. Playwright)
- Designed to be set up with the help of [Claude Code](https://claude.com/claude-code): point it at your CV, it drafts your `config.yaml`, you review and run

MIT licensed. See [LICENSE](./LICENSE).
