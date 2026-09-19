"""
Filtros duros: un aviso que no pasa esto se descarta, sin importar el score.

Toda la lógica de detección de "hybrid/presencial disfrazado de remote" y
"geo-lock" viene de la sesión donde armamos esto originalmente: la primera
versión del buscador confiaba en el resumen de LinkedIn (que dice "Remote"
aunque el aviso real sea híbrido) y eso generó falsos positivos. La función
`verify_remote_from_full_text` está para cuando tenés la descripción
completa del aviso (no solo el resumen de búsqueda) — usala si podés pagar
el costo de fetchear cada URL individualmente antes del filtrado final.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sources.ats import RawJob

GEO_LOCK_RE = re.compile(
    r"\b(us\s*only|u\.s\.\s*only|united\s*states\s*only|us\s+citizens?\s+only|"
    r"must\s+(be\s+)?(based|located|resident|reside)\s+in\s+(the\s+)?"
    r"(us|usa|united\s*states|europe|emea)|eu\s*only|europe\s*only|emea\s*only|"
    r"europe-based|uk-based|us-based|india\s*only|india-based|canada\s*only|apac\s*only)\b",
    re.I,
)

HYBRID_ONSITE_RE = re.compile(
    r"\b(hybrid|híbrid[oa]|hibrid[oa]|on-?site|presencial|in-?person|"
    r"in-?office|office-?based|on-?premise[s]?)\b",
    re.I,
)

REMOTE_OVERRIDE_RE = re.compile(
    r"\b(100%\s*remot[eo]|fully\s*remot[eo]|remote(-|\s*)only|remote(-|\s*)first|"
    r"solo\s+remot[eo]|work\s*from\s*(home|anywhere)|remote\s*[-–]\s*global|"
    r"teletrabajo|distributed\s+team)\b",
    re.I,
)


@dataclass
class FilterConfig:
    ban_title_keywords: list[str]
    require_junior_signal: bool
    years_experience_max: int | None
    location_mode: str
    home_city: str
    allowed_countries: list[str]
    accept_scopes: list[str]
    reject_hybrid: bool
    reject_onsite: bool
    banned_locations: list[str]
    geo_lock_reject: bool
    banned_companies: list[str]
    title_exclude_keywords: list[str]
    title_require_keywords: list[str]
    blacklist_urls: set[str]

    @classmethod
    def from_yaml(cls, cfg: dict, blacklist_urls: set[str]) -> "FilterConfig":
        f = cfg["filters"]
        sen = f["seniority"]
        loc = f["location"]
        return cls(
            ban_title_keywords=sen.get("ban_title_keywords", []),
            require_junior_signal=sen.get("require_junior_signal", False),
            years_experience_max=sen.get("years_experience_max"),
            location_mode=loc.get("mode", "any"),
            home_city=(loc.get("home_city") or "").lower(),
            allowed_countries=[c.lower() for c in loc.get("allowed_countries", [])],
            accept_scopes=loc.get("accept_scopes", ["global", "region", "country"]),
            reject_hybrid=loc.get("reject_hybrid", True),
            reject_onsite=loc.get("reject_onsite", True),
            banned_locations=[b.lower() for b in loc.get("banned_locations", [])],
            geo_lock_reject=loc.get("geo_lock_reject", True),
            banned_companies=[c.lower() for c in f.get("companies", {}).get("banned", [])],
            title_exclude_keywords=f.get("title_exclude_keywords", []),
            title_require_keywords=f.get("title_require_keywords", []),
            blacklist_urls=blacklist_urls,
        )


def _years_too_much(text: str, max_years: int | None) -> bool:
    if max_years is None:
        return False
    pattern = re.compile(
        rf"\b(([{max_years}-9]|1\d)\+?\s*[-–\s]*\s*(years?|yrs?|años|anos?)|"
        rf"(at\s+least|minimum|min\.?|más\s+de|mas\s+de|over)\s+([{max_years}-9]|1\d)\s*(years?|yrs?|años))\b",
        re.I,
    )
    return bool(pattern.search(text))


def _loc_tag(job: RawJob, cfg: FilterConfig) -> tuple[bool, str]:
    blob = f"{job.location} {job.description[:1500]}".lower()
    title = job.title.lower()

    if cfg.geo_lock_reject and GEO_LOCK_RE.search(blob):
        return False, "geo_lock"

    for banned in cfg.banned_locations:
        if banned in blob:
            return False, "banned_location"

    if cfg.home_city and cfg.home_city in blob:
        return True, "home_city"

    if cfg.reject_hybrid or cfg.reject_onsite:
        h = HYBRID_ONSITE_RE.search(title) or HYBRID_ONSITE_RE.search(blob)
        if h and not REMOTE_OVERRIDE_RE.search(blob):
            return False, "hybrid_onsite"

    if cfg.location_mode == "any":
        return True, "any"

    global_remote = re.search(
        r"\b(worldwide|anywhere|remote\s+global|global\s+remote|100%\s*remote|fully\s*remote)\b",
        blob,
    )
    if "global" in cfg.accept_scopes and global_remote:
        return True, "global_remote"

    for country in cfg.allowed_countries:
        if country in blob and "country" in cfg.accept_scopes:
            remote_signal = re.search(r"remot[eo]|work from home|home office|teletrabajo", blob)
            if remote_signal:
                return True, "country_remote"

    if cfg.location_mode == "remote_or_home_city":
        return False, "not_remote"

    return False, "not_remote"


def passes_filters(job: RawJob, cfg: FilterConfig) -> tuple[bool, str]:
    if not job.title or len(job.title) < 5:
        return False, "no_title"

    if job.url in cfg.blacklist_urls or job.url.rstrip("/") in cfg.blacklist_urls:
        return False, "blacklisted"

    if job.company.lower() in cfg.banned_companies:
        return False, "banned_company"

    title = job.title
    for kw in cfg.ban_title_keywords:
        if re.search(kw, title, re.I):
            return False, "banned_title_keyword"

    for kw in cfg.title_exclude_keywords:
        if re.search(re.escape(kw), title, re.I):
            return False, "title_excluded"

    if cfg.title_require_keywords:
        if not any(re.search(re.escape(kw), title, re.I) for kw in cfg.title_require_keywords):
            return False, "missing_required_keyword"

    if cfg.require_junior_signal:
        junior_re = re.compile(r"\b(junior|jr\.?|entry|trainee|graduate|intern|apprentice)\b", re.I)
        if not junior_re.search(title):
            return False, "not_junior"

    full_text = f"{title} {job.description}"
    if _years_too_much(full_text, cfg.years_experience_max):
        return False, "years_experience"

    ok, tag = _loc_tag(job, cfg)
    if not ok:
        return False, f"location:{tag}"
    job.tags.append(f"loc:{tag}")

    return True, tag


def apply_filters(jobs: list[RawJob], cfg: FilterConfig) -> tuple[list[RawJob], dict[str, int]]:
    kept = []
    rejected: dict[str, int] = {}
    seen_keys = set()

    for job in jobs:
        key = (job.title.lower().strip()[:80], job.company.lower().strip()[:40])
        if key in seen_keys:
            continue
        seen_keys.add(key)

        ok, reason = passes_filters(job, cfg)
        if ok:
            kept.append(job)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1

    return kept, rejected


def verify_remote_from_full_text(job: RawJob, full_page_text: str) -> tuple[bool, str]:
    """
    Verificación estricta usando el texto REAL de la página del aviso
    (no el resumen de búsqueda). Fetcheá cada URL individualmente y pasale
    el HTML/texto acá antes de confiar en el resultado — así evitás el
    problema que tuvimos donde LinkedIn decía "remote" en el resumen pero
    el aviso real era híbrido/presencial.
    """
    blob = full_page_text.lower()
    if HYBRID_ONSITE_RE.search(blob) and not REMOTE_OVERRIDE_RE.search(blob):
        m = HYBRID_ONSITE_RE.search(blob)
        return False, f"hybrid_onsite_confirmed:{m.group(0)}"
    if GEO_LOCK_RE.search(blob):
        return False, "geo_lock_confirmed"
    return True, "ok"
