"""
Fetchers for public ATS APIs (Greenhouse, Ashby, Lever).

These three are documented APIs, meant so anyone can list a company's
public job postings without authentication. No HTML scraping here — these
are stable JSON endpoints.

How to find a company's "slug":
  - Greenhouse: their careers URL is usually boards.greenhouse.io/<slug>
    or job-boards.greenhouse.io/<slug>
  - Ashby: jobs.ashbyhq.com/<slug>
  - Lever: jobs.lever.co/<slug>
If you're not sure, try all three — whichever doesn't apply just returns
an empty list or a 404, it won't break anything.
"""
from __future__ import annotations

import concurrent.futures as cf
from dataclasses import dataclass, field

import requests

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
TIMEOUT = 10


@dataclass
class RawJob:
    source: str
    company: str
    title: str
    location: str
    url: str
    description: str = ""
    posted: str = ""
    tags: list = field(default_factory=list)


def _get_json(url: str) -> dict | list | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def fetch_greenhouse(slug: str) -> list[RawJob]:
    d = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not d or not isinstance(d, dict):
        return []
    out = []
    for job in d.get("jobs", []):
        loc_obj = job.get("location") or {}
        loc = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)
        offices = [(o.get("name") or "") for o in (job.get("offices") or [])]
        depts = ", ".join((dp.get("name") or "") for dp in (job.get("departments") or []))
        out.append(RawJob(
            source="Greenhouse",
            company=slug,
            title=job.get("title") or "",
            location=loc or ", ".join(offices) or "Not specified",
            url=job.get("absolute_url") or "",
            description=f"{depts} | {loc} | offices: {', '.join(offices)}",
            posted=job.get("updated_at") or job.get("first_published") or "",
            tags=[depts] if depts else [],
        ))
    return out


def fetch_ashby(slug: str) -> list[RawJob]:
    d = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not d or not isinstance(d, dict):
        return []
    out = []
    for job in d.get("jobs", []):
        loc = job.get("location") or ""
        if isinstance(loc, list):
            loc = ", ".join(loc)
        wtype = job.get("workplaceType") or ""
        dept = job.get("department") or job.get("team") or ""
        out.append(RawJob(
            source="Ashby",
            company=slug,
            title=job.get("title") or "",
            location=f"{loc} [{wtype}]".strip(),
            url=job.get("jobUrl") or job.get("applyUrl") or "",
            description=f"{dept} | {job.get('employmentType', '')} | {wtype}",
            posted=job.get("publishedAt") or job.get("updatedAt") or "",
            tags=[dept] if dept else [],
        ))
    return out


def fetch_lever(slug: str) -> list[RawJob]:
    d = _get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not d or not isinstance(d, list):
        return []
    out = []
    for job in d:
        cat = job.get("categories") or {}
        loc = cat.get("location") or cat.get("allLocations") or ""
        if isinstance(loc, list):
            loc = ", ".join(loc)
        out.append(RawJob(
            source="Lever",
            company=slug,
            title=job.get("text") or "",
            location=loc or "Not specified",
            url=job.get("hostedUrl") or job.get("applyUrl") or "",
            description=f"{cat.get('team', '')} | {cat.get('commitment', '')}",
            posted="",  # Lever provides a ms timestamp under 'createdAt' if you want to parse it
            tags=[cat.get("team", "")],
        ))
    return out


FETCHERS = {"greenhouse": fetch_greenhouse, "ashby": fetch_ashby, "lever": fetch_lever}


def fetch_companies(companies: list[dict], requests_per_batch: int = 40) -> list[RawJob]:
    """
    companies: [{"slug": "some-company", "boards": ["ashby"]}, ...]
    Runs every (company, board) combination in parallel with a bounded
    pool, so it doesn't overload your connection or the remote server.
    """
    tasks = []
    for c in companies:
        slug = c["slug"]
        for board in c.get("boards", ["greenhouse", "ashby", "lever"]):
            fn = FETCHERS.get(board)
            if fn:
                tasks.append((fn, slug))

    results: list[RawJob] = []
    with cf.ThreadPoolExecutor(max_workers=requests_per_batch) as ex:
        futures = {ex.submit(fn, slug): (fn.__name__, slug) for fn, slug in tasks}
        for fut in cf.as_completed(futures):
            try:
                results.extend(fut.result())
            except Exception:
                pass
    return results
