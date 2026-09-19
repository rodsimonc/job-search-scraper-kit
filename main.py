#!/usr/bin/env python3
"""
Buscador de empleo configurable — punto de entrada.

Uso:
    python main.py                       # usa config.yaml en esta carpeta
    python main.py --config otro.yaml    # usa otro archivo de config
    python main.py --save-blacklist      # agrega las URLs de este resultado
                                          # al blacklist_urls_file, para que
                                          # la próxima corrida no las repita

Requiere: pip install -r requirements.txt
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

from sources import ats, linkedin, regional
from sources.ats import RawJob
import filters as filters_mod
import scoring as scoring_mod


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def load_blacklist(path: str) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    urls = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            urls.add(line)
            urls.add(line.rstrip("/"))
    return urls


def collect_jobs(cfg: dict) -> list[RawJob]:
    jobs: list[RawJob] = []
    src = cfg["sources"]

    if src.get("ats", {}).get("enabled"):
        companies = src["ats"].get("companies") or []
        if not companies:
            print("[ats] enabled pero sin 'companies' en config.yaml — saltando", file=sys.stderr)
        else:
            print(f"[ats] buscando en {len(companies)} empresas...")
            batch = src["ats"].get("requests_per_batch", 40)
            found = ats.fetch_companies(companies, requests_per_batch=batch)
            print(f"[ats] {len(found)} avisos encontrados")
            jobs.extend(found)

    if src.get("linkedin", {}).get("enabled"):
        li = src["linkedin"]
        if not li.get("keywords") or not li.get("locations"):
            print("[linkedin] enabled pero faltan 'keywords' o 'locations' — saltando", file=sys.stderr)
        else:
            print(f"[linkedin] buscando {len(li['keywords'])} keywords x {len(li['locations'])} ubicaciones...")
            found = linkedin.fetch(
                keywords=li["keywords"],
                locations=li["locations"],
                time_range_days=li.get("time_range_days", 7),
                experience_levels=li.get("experience_levels") or None,
                max_requests=li.get("max_requests", 150),
                delay_seconds=li.get("delay_seconds", 0.3),
            )
            print(f"[linkedin] {len(found)} avisos encontrados")
            jobs.extend(found)

    regional_cfg = src.get("regional_portals", {})
    if regional_cfg.get("getonboard", {}).get("enabled"):
        gob = regional_cfg["getonboard"]
        print(f"[getonboard] buscando en {gob.get('countries')}...")
        found = regional.fetch_getonboard(
            countries=gob.get("countries", []),
            categories=gob.get("categories", ["programming"]),
        )
        print(f"[getonboard] {len(found)} avisos encontrados")
        jobs.extend(found)

    for name, fn in [
        ("computrabajo", regional.fetch_computrabajo),
        ("bumeran", regional.fetch_bumeran),
        ("zonajobs", regional.fetch_zonajobs),
        ("trabajo_org", regional.fetch_trabajo_org),
    ]:
        if regional_cfg.get(name, {}).get("enabled"):
            try:
                jobs.extend(fn())
            except NotImplementedError as e:
                print(f"[{name}] {e}", file=sys.stderr)

    return jobs


def write_markdown(scored: list[tuple[RawJob, int, list[str]]], jobs_total: int, kept_total: int, rejected: dict, path: str):
    lines = [
        "# Resultados de búsqueda\n",
        f"- Avisos crudos recolectados: **{jobs_total}**",
        f"- Después de deduplicar + filtros: **{kept_total}**",
        f"- Mostrados: **{len(scored)}**",
        "",
        "## Motivos de rechazo",
        "",
    ]
    for reason, count in sorted(rejected.items(), key=lambda x: -x[1]):
        lines.append(f"- {reason}: {count}")
    lines += [
        "",
        "## Ranking",
        "",
        "| # | Score | Título | Empresa | Ubicación | Fuente | URL |",
        "|---|------:|--------|---------|-----------|--------|-----|",
    ]
    for i, (job, s, reasons) in enumerate(scored, 1):
        t = job.title[:60].replace("|", "\\|")
        c = job.company[:25].replace("|", "\\|")
        l = job.location[:30].replace("|", "\\|")
        lines.append(f"| {i} | {s} | {t} | {c} | {l} | {job.source} | [link]({job.url}) |")

    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_csv(scored: list[tuple[RawJob, int, list[str]]], path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "title", "company", "location", "source", "url", "posted"])
        for job, s, _ in scored:
            w.writerow([s, job.title, job.company, job.location, job.source, job.url, job.posted])


def write_json(scored: list[tuple[RawJob, int, list[str]]], path: str):
    data = [
        {
            "score": s,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "source": job.source,
            "url": job.url,
            "posted": job.posted,
            "reasons": reasons,
        }
        for job, s, reasons in scored
    ]
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--save-blacklist", action="store_true",
                         help="Agrega las URLs de este resultado al blacklist_urls_file")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print(f"No encontré {args.config}. Copiá config.example.yaml a config.yaml y completalo primero.",
              file=sys.stderr)
        sys.exit(1)

    cfg = load_config(args.config)

    blacklist_path = cfg["filters"].get("blacklist_urls_file", "./blacklist.txt")
    blacklist = load_blacklist(blacklist_path)
    print(f"Blacklist cargada: {len(blacklist)} URLs")

    raw_jobs = collect_jobs(cfg)
    print(f"\nTotal avisos crudos: {len(raw_jobs)}")

    filter_cfg = filters_mod.FilterConfig.from_yaml(cfg, blacklist)
    kept, rejected = filters_mod.apply_filters(raw_jobs, filter_cfg)
    print(f"Después de filtros: {len(kept)}")
    for reason, count in sorted(rejected.items(), key=lambda x: -x[1])[:10]:
        print(f"  rechazados por {reason}: {count}")

    scored = scoring_mod.score_and_sort(kept, cfg)

    out = cfg.get("output", {})
    fmt = out.get("format", "markdown")
    out_path = out.get("path", "./resultados.md")

    if fmt == "markdown":
        write_markdown(scored, len(raw_jobs), len(kept), rejected, out_path)
    elif fmt == "csv":
        write_csv(scored, out_path)
    elif fmt == "json":
        write_json(scored, out_path)
    else:
        print(f"Formato desconocido: {fmt}", file=sys.stderr)
        sys.exit(1)

    print(f"\nEscribí {len(scored)} resultados en {out_path}")

    if args.save_blacklist:
        with open(blacklist_path, "a", encoding="utf-8") as f:
            for job, _, _ in scored:
                f.write(job.url + "\n")
        print(f"Agregué {len(scored)} URLs a {blacklist_path} para no repetirlas la próxima vez")


if __name__ == "__main__":
    main()
