"""
Scoring: ordena lo que ya pasó los filtros duros. No descarta nada, solo
define qué aparece primero en el reporte.
"""
from __future__ import annotations

import re

from sources.ats import RawJob


def score_job(job: RawJob, cfg: dict) -> tuple[int, list[str]]:
    sc = cfg["scoring"]
    tag_str = " ".join(str(t) for t in job.tags)
    blob = f"{job.title} {tag_str} {job.description[:800]}".lower()
    title = job.title.lower()

    total = 0
    reasons = []

    for kw, weight in sc.get("stack_weights", {}).items():
        if kw.lower() in blob:
            total += weight
            if weight >= 4:
                reasons.append(f"+{weight} {kw}")

    for kw, weight in sc.get("negative_stack_weights", {}).items():
        if kw.lower() in blob:
            total += weight

    title_bonus = sc.get("title_bonus", {})
    for kw in title_bonus.get("keywords", []):
        if re.search(re.escape(kw), title, re.I):
            bonus = title_bonus.get("bonus", 0)
            total += bonus
            reasons.append(f"+{bonus} title:{kw}")
            break

    loc_bonus_cfg = sc.get("location_bonus", {})
    loc_tag = next((t.split(":", 1)[1] for t in job.tags if t.startswith("loc:")), None)
    loc_bonus_map = {
        "home_city": loc_bonus_cfg.get("home_city", 0),
        "country_remote": loc_bonus_cfg.get("country_remote", 0),
        "region_remote": loc_bonus_cfg.get("region_remote", 0),
        "global_remote": loc_bonus_cfg.get("global_remote", 0),
    }
    if loc_tag in loc_bonus_map:
        b = loc_bonus_map[loc_tag]
        total += b
        reasons.append(f"+{b} {loc_tag}")

    return total, reasons


def score_and_sort(jobs: list[RawJob], cfg: dict) -> list[tuple[RawJob, int, list[str]]]:
    scored = []
    for job in jobs:
        s, reasons = score_job(job, cfg)
        scored.append((job, s, reasons))
    scored.sort(key=lambda x: -x[1])
    top_n = cfg["scoring"].get("top_n", 200)
    return scored[:top_n]
