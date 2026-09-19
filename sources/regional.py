"""
Portales regionales (LATAM).

Estado de cada uno, honesto:

  - GetOnBoard: IMPLEMENTADO Y PROBADO. Tiene una API JSON pública
    (www.getonbrd.com/api/v0/...) que no requiere autenticación.

  - Computrabajo, Bumeran, ZonaJobs, Trabajo.org: NO IMPLEMENTADOS.
    Los probamos en la sesión donde armamos esto y son SPAs (Angular/React)
    modernas — el HTML que devuelve un curl/requests normal no contiene
    los avisos, sólo el shell de la app. Para scrapearlos de verdad hace
    falta un browser real (Playwright o Selenium) que ejecute el JS y
    espere a que la lista cargue. Quedan como funciones que devuelven
    NotImplementedError con instrucciones de qué falta, en vez de fallar
    en silencio o devolver datos falsos.

Categorías válidas de GetOnBoard (para `categories` en config.yaml):
  programming, design, data-science-analytics, devops-sysadmin,
  qa-testing, mobile-developer, product, marketing, sales,
  customer-service, business-management, hr
"""
from __future__ import annotations

import requests

from .ats import RawJob, USER_AGENT, TIMEOUT

GOB_SENIORITY_JUNIOR_IDS = {2, 3}   # 2=junior, 3=semi-senior (ver nota abajo)
GOB_MODALITY_REMOTE_ID = 2           # 1=hybrid, 2=fully_remote, 3=onsite


def fetch_getonboard(countries: list[str], categories: list[str], only_remote: bool = True) -> list[RawJob]:
    """
    NOTA sobre los IDs de seniority/modality: GetOnBoard no los expone como
    texto en la respuesta, son IDs numéricos (1..5 para seniority, 1..3 para
    modality) que dedujimos empíricamente mirando varios avisos conocidos.
    Si notás que el filtro no está clasificando bien, revisá una respuesta
    cruda de la API y ajustá estos sets.
    """
    out = []
    for country in countries:
        for cat in categories:
            for page in range(1, 5):  # hasta 4 páginas por combinación
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
            f"{name} no está implementado en este kit. {what_it_needs}\n"
            f"Si lo necesitás: escribí un fetcher en sources/regional.py que "
            f"use Playwright (pip install playwright && playwright install chromium) "
            f"para renderizar la página, esperar a que carguen los resultados, y "
            f"extraer título/empresa/ubicación/URL de cada card. Podés pedirle a "
            f"Claude Code que lo escriba mostrándole la URL de búsqueda del portal."
        )
    return _fn


fetch_computrabajo = _not_implemented(
    "Computrabajo",
    "Es una SPA; el listado de resultados se arma client-side con JS.",
)
fetch_bumeran = _not_implemented(
    "Bumeran",
    "Misma situación que Computrabajo — requiere browser real.",
)
fetch_zonajobs = _not_implemented(
    "ZonaJobs",
    "Misma situación — requiere browser real.",
)
fetch_trabajo_org = _not_implemented(
    "Trabajo.org",
    "Expone páginas de categoría pero no las cards de avisos individuales vía HTML plano.",
)
