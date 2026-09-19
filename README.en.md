# Configurable job search kit

**[Leer esto en español →](./README.es.md)**

This kit searches job postings across several sources (company ATS boards,
LinkedIn, regional job portals), filters them by your own criteria, and
scores/ranks the results. It was originally built with the help of
[Claude Code](https://claude.com/claude-code) for a real job search, then
packaged so anyone can adapt it to their own.

## Where this comes from

This isn't a scraping technique invented from scratch. It's a
**combination** of publicly known approaches for each source — the ATS
endpoints are APIs documented by their own providers; the pattern for
scraping LinkedIn's guest endpoint has been floating around the community
for years — **plus a set of adaptations** that turned out to matter after
actually using this in a real search: detecting "hybrid dressed up as
remote," carrying a blacklist across runs so you don't see the same posting
twice, deduplication by title+company, and a scoring system that's fully
configurable through YAML. The value this repo adds is having packaged all
of that into something reusable and easy to adapt — not the scraping
technique itself, which is public domain.

> **Legal notice / disclaimer**
> This project is shared "as is", with no warranty of any kind (see
> [LICENSE](./LICENSE)). The `sources/linkedin.py` module scrapes a public
> LinkedIn endpoint (no login required) that **technically violates their
> Terms of Service** — it ships disabled by default (`enabled: false`), and
> whether to turn it on is each user's own decision and responsibility. The
> ATS modules (Greenhouse/Ashby/Lever) and GetOnBoard use public APIs
> documented by each provider, with no such issue. More detail in the
> [About LinkedIn](#about-linkedin) section below.

## Requirements

- Python 3.10+
- Your CV as a PDF (optional, but helps with step 2)
- [Claude Code](https://claude.com/claude-code) installed — the workflow
  below is built around it, though you can also fill in the config by hand
  without it.

## How to run it (with Claude Code)

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set up your config**

Copy `config.example.en.yaml` to `config.yaml` and drop your CV in this
folder (e.g. `my_cv.pdf`). (If you'd rather work from the Spanish template,
use `config.example.es.yaml` — same keys, only the comments differ.)

Open this folder with Claude Code (run `claude` in a terminal, from inside
this directory) and tell it something like:

> Read my CV at ./my_cv.pdf and fill in config.yaml:
> 1. Suggest 15-20 companies relevant to my profile for the
>    sources.ats.companies section (with their Greenhouse/Ashby/Lever slugs)
> 2. Build scoring.stack_weights from the technologies/skills in my CV,
>    weighting more heavily whatever defines me best
> 3. Adjust filters.seniority, filters.location and filters.companies.banned
>    based on what I tell you about my search (level, location, exclusions)
>
> My search is: [describe in a line or two what you're looking for — role,
> work mode, location, anything relevant]

Claude Code will read the PDF and edit `config.yaml` directly. **Review it
yourself before running anything** — it's a starting point, not a final
answer. Nobody knows your search better than you do.

**3. Run the search**

```bash
python main.py
```

This will:
1. Search every source you enabled (`enabled: true`)
2. Deduplicate and apply the hard filters
3. Score and sort whatever survived
4. Write the result to `results.md` (or `.csv`/`.json`, depending on
   `output.format`)

**4. Later runs**

If you run this again later and don't want to see the same postings:

```bash
python main.py --save-blacklist
```

This saves the current result's URLs to `blacklist.txt`, and the next run
excludes them automatically.

## Kit structure

```
job-search-scraper-kit/
├── README.md                  # bilingual landing page
├── README.es.md               # Spanish version
├── README.en.md               # this file
├── config.example.es.yaml     # config template, Spanish
├── config.example.en.yaml     # config template, English
├── main.py                    # orchestrator: gathers sources, filters, scores, writes output
├── filters.py                 # hard filters (seniority, location, blacklist)
├── scoring.py                 # keyword/weight-based scoring
├── requirements.txt
└── sources/
    ├── ats.py                 # Greenhouse / Ashby / Lever — tested, stable
    ├── linkedin.py             # LinkedIn jobs-guest API — see warning below
    └── regional.py             # GetOnBoard (tested) + stubs for other portals
```

The code (`.py` files) has English comments, following standard open-source
convention — only the documentation (README, config) is duplicated in both
languages.

## Sources: what's tested and what isn't

| Source | Status | Notes |
|---|---|---|
| Greenhouse / Ashby / Lever | ✅ Tested, stable | Public APIs documented by each provider. No risk of being blocked. |
| LinkedIn (jobs-guest) | ⚠️ Works, but outside ToS | See warning above and below. |
| GetOnBoard | ✅ Tested, stable | Public JSON API, LATAM countries. |
| Computrabajo / Bumeran / ZonaJobs / Trabajo.org | ❌ Not implemented | These are SPAs — they need Playwright/Selenium to render JS. Left as documented stubs in `sources/regional.py`. |

### About LinkedIn

The endpoint `sources/linkedin.py` uses is the same one search engines use
to index public postings — it doesn't require login or credentials. Even
so, automated scraping of LinkedIn violates its Terms of Service. In
practice:

- LinkedIn can temporarily block your IP if you make too many requests in a
  short time (that's what `max_requests` and `delay_seconds` in the config
  are for — respect them)
- The endpoint can change without notice
- A real problem we ran into while using this: LinkedIn's search summary
  can say "remote" for a posting that's actually hybrid or on-site. If
  accuracy matters to you, don't rely solely on `main.py`'s output — open
  each final URL and check the full description before applying.
  `filters.verify_remote_from_full_text()` exists to automate that second
  pass if you want it (fetch each URL, pass it the text, and it tells you
  whether "remote" is real).

Leave it at `enabled: false` in the config if you'd rather not take that
risk — ATS sources + GetOnBoard alone already give you a solid, 100% legal
baseline.

## How scoring works

`scoring.py` does NOT decide what gets dropped (that's `filters.py`'s job,
earlier in the pipeline) — it only sorts whatever survived the filters.
Each posting earns points for:

- Matching your stack keywords (`scoring.stack_weights`)
- Losing points if an unwanted technology shows up (`scoring.negative_stack_weights`)
- A bonus if the title contains a seniority keyword you're looking for
  (`scoring.title_bonus`)
- A bonus based on how well the location matches
  (`scoring.location_bonus`: your city > country-remote > region-remote > global-remote)

All of that is 100% editable in `config.yaml` — nothing is hardcoded in the
code; the weights are data, not logic.

## Extending this

- **Adding a new portal**: write a function in `sources/regional.py` that
  returns a list of `RawJob` (see `fetch_getonboard` for an example against
  a real JSON API). If the portal is a SPA, you'll need Playwright. You can
  ask Claude Code to write it for you — give it the portal's search URL and
  an example of the postings you expect to see.
- **Changing filter logic**: it all lives in `filters.py`, with explicit,
  commented regexes — nothing hidden behind an external library.
- **Changing the output format**: add a `write_<format>` function in
  `main.py` following the `write_markdown`/`write_csv`/`write_json` pattern.

## Known limitations

- Scoring and filtering work off the title + short description each source
  returns up front — they don't fetch the full posting page unless you call
  `verify_remote_from_full_text` manually. That means some postings whose
  full description differs from the summary can slip through or get
  wrongly excluded.
- `sources/regional.py` has 4 portals left unimplemented — not bugs, they're
  documented as such.
- GetOnBoard's numeric seniority/modality IDs (`GOB_SENIORITY_JUNIOR_IDS`,
  `GOB_MODALITY_REMOTE_ID` in `sources/regional.py`) were reverse-engineered
  by testing known postings, not officially documented by GetOnBoard — if
  you notice odd results, that's the first place to check.

## Contributing

PRs welcome, especially to implement any of the regional portals left as
stubs, or to add new sources.
