"""
Regional portals (LATAM).

Honest status of each one:

  - GetOnBoard: IMPLEMENTED AND TESTED. Has a public JSON API
    (www.getonbrd.com/api/v0/...) that doesn't require authentication.

  - Computrabajo, Bumeran, ZonaJobs, Trabajo.org: NOT IMPLEMENTED.
    We tried these while building this kit and they're modern
    (Angular/React) SPAs — the HTML a plain curl/requests call returns
    doesn't contain the postings, only the app shell. Scraping them for
    real requires an actual browser (Playwright or Selenium) that runs
    the JS and waits for the list to load. They're left as functions that
    raise NotImplementedError with instructions on what's missing, rather
    than failing silently or returning fake data.

Valid GetOnBoard categories (for `categories` in config.yaml):
  programming, design, data-science-analytics, devops-sysadmin,
  qa-testing, mobile-developer, product, marketing, sales,
  customer-service, business-management, hr
"""
from __future__ import annotations

import requests

from .ats import RawJob, USER_AGENT, TIMEOUT

GOB_SENIORITY_JUNIOR_IDS = {2, 3}   # 2=junior, 3=semi-senior (see note below)
GOB_MODALITY_REMOTE_ID = 2           # 1=hybrid, 2=fully_remote, 3=onsite


def fetch_getonboard(countries: list[str], categories: list[str], only_remote: bool = True) -> list[RawJob]:
    """
    Note on the seniority/modality IDs: GetOnBoard doesn't expose them as
    text in the response, they're numeric IDs (1..5 for seniority, 1..3 for
    modality) that we reverse-engineered by looking at several known
    postings. If you notice the filter isn't classifying things correctly,
    check a raw API response and adjust these sets.
    """
    out = []
    for country in countries:
        for cat in categories:
            for page in range(1, 5):  # up to 4 pages per combination
                url = (
                    f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs"
                    f"?per_page=100&page={page}&country={country}"
                )
                try:
                    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
                    if r.status_code != 200:
                        break
                    d = r.json()
                except Exception:
                    break

                data = d.get("data", [])
                if not data:
                    break

                for e in data:
                    a = e.get("attributes", {})
                    if only_remote:
                        mod_id = (a.get("modality") or {}).get("data", {}).get("id")
                        if mod_id != GOB_MODALITY_REMOTE_ID:
                            continue
                    out.append(RawJob(
                        source="GetOnBoard",
                        company="",
                        title=a.get("title") or "",
                        location=f"{country} [REMOTE]" if only_remote else country,
                        url=f"https://www.getonbrd.com/jobs/{e.get('id')}",
                        description=(a.get("description") or "")[:800],
                        posted=str(a.get("published_at") or ""),
                        tags=a.get("tags") or [],
                    ))
    return out


def _not_implemented(name: str, what_it_needs: str):
    def _fn(*_args, **_kwargs):
        raise NotImplementedError(
            f"{name} is not implemented in this kit. {what_it_needs}\n"
            f"If you need it: write a fetcher in sources/regional.py using "
            f"Playwright (pip install playwright && playwright install chromium) "
            f"to render the page, wait for the results to load, and extract "
            f"title/company/location/URL from each card. You can ask Claude "
            f"Code to write it for you by showing it the portal's search URL."
        )
    return _fn


fetch_computrabajo = _not_implemented(
    "Computrabajo",
    "It's a SPA; the results list is built client-side with JS.",
)
fetch_bumeran = _not_implemented(
    "Bumeran",
    "Same situation as Computrabajo — needs a real browser.",
)
fetch_zonajobs = _not_implemented(
    "ZonaJobs",
    "Same situation — needs a real browser.",
)
fetch_trabajo_org = _not_implemented(
    "Trabajo.org",
    "Exposes category pages but not individual posting cards via plain HTML.",
)
