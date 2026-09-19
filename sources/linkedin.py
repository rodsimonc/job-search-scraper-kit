"""
Fetcher del endpoint público "jobs-guest" de LinkedIn (el mismo que usan
los buscadores para indexar avisos, no requiere login).

⚠️  LEER ANTES DE ACTIVAR (linkedin.enabled: true en config.yaml):
    El scraping automatizado de LinkedIn, aunque sea de contenido público
    y sin login, va contra sus Términos de Servicio. En la práctica:
      - Es de lectura únicamente, no hace login ni usa credenciales
      - LinkedIn puede banear temporalmente tu IP si hacés demasiadas
        requests en poco tiempo (por eso existen max_requests y delay_seconds
        en la config — respetalos)
      - No hay garantía de que este endpoint siga funcionando igual en el
        futuro; LinkedIn lo cambia sin aviso
    Usalo bajo tu propio criterio y responsabilidad.
"""
from __future__ import annotations

import html
import re
import time
from urllib.parse import quote

import requests

from .ats import RawJob, USER_AGENT, TIMEOUT

BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# f_TPR: r86400=1 día, r604800=7 días, r2592000=30 días
_TPR_MAP = {1: "r86400", 7: "r604800", 30: "r2592000"}


def _clean(t: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(t or ""))).strip()


def _parse_page(txt: str, seen_ids: set[str]) -> list[RawJob]:
    out = []
    blocks = re.split(r"<li>\s*\n", txt)
    for b in blocks:
        m_id = re.search(r"urn:li:jobPosting:(\d+)", b)
        if not m_id:
            continue
        jid = m_id.group(1)
        if jid in seen_ids:
            continue
        seen_ids.add(jid)
        m_title = re.search(r'base-search-card__title">\s*(.+?)\s*</h3>', b, re.S)
        m_comp = re.search(r'base-search-card__subtitle">.*?<a[^>]*>\s*(.+?)\s*</a>', b, re.S)
        m_loc = re.search(r'job-search-card__location">\s*(.+?)\s*</span>', b, re.S)
        m_href = re.search(r'href="(https://[^"]*?/jobs/view/[^"]+)"', b)
        m_time = re.search(r'datetime="([^"]+)"', b)
        out.append(RawJob(
            source="LinkedIn",
            company=_clean(m_comp.group(1) if m_comp else ""),
            title=_clean(m_title.group(1) if m_title else ""),
            location=_clean(m_loc.group(1) if m_loc else ""),
            url=(m_href.group(1).split("?")[0] if m_href else f"https://www.linkedin.com/jobs/view/{jid}"),
            posted=m_time.group(1) if m_time else "",
        ))
    return out


def fetch(
    keywords: list[str],
    locations: list[str],
    time_range_days: int = 7,
    experience_levels: list[str] | None = None,
    max_requests: int = 150,
    delay_seconds: float = 0.3,
    pages_per_query: int = 1,
) -> list[RawJob]:
    """
    Recorre keywords x locations (x páginas si pages_per_query > 1) contra
    el endpoint guest de LinkedIn. Corta apenas llega a max_requests, así
    tenés un techo duro sin importar cuántas combinaciones definiste.
    """
    tpr = _TPR_MAP.get(time_range_days, "r604800")
    exp = ",".join(experience_levels) if experience_levels else None

    seen_ids: set[str] = set()
    results: list[RawJob] = []
    requests_made = 0

    for kw in keywords:
        for loc in locations:
            for page in range(pages_per_query):
                if requests_made >= max_requests:
                    return results
                start = page * 25
                url = (
                    f"{BASE}?keywords={quote(kw)}&location={quote(loc)}"
                    f"&f_TPR={tpr}&f_WT=2&start={start}"
                )
                if exp:
                    url += f"&f_E={exp}"
                try:
                    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
                    requests_made += 1
                    if r.status_code == 200:
                        results.extend(_parse_page(r.text, seen_ids))
                except Exception:
                    pass
                time.sleep(delay_seconds)

    return results
