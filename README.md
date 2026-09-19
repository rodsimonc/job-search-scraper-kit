# Buscador de empleo configurable

Este kit busca avisos de trabajo en varias fuentes (ATS de empresas,
LinkedIn, portales regionales), los filtra según tus criterios, y los
ordena por score. Nació de una búsqueda puntual armada con [Claude Code](https://claude.com/claude-code)
y lo empaquetamos para que cualquiera pueda adaptarlo a la suya.

> **Aviso legal / de responsabilidad**
> Este proyecto se comparte "tal cual", sin garantía de ningún tipo (ver
> [LICENSE](./LICENSE)). El módulo `sources/linkedin.py` scrapea un
> endpoint público de LinkedIn (sin login) que **técnicamente va contra sus
> Términos de Servicio** — viene desactivado por defecto (`enabled: false`)
> y es decisión y responsabilidad de cada usuario activarlo o no. Los
> módulos de ATS (Greenhouse/Ashby/Lever) y GetOnBoard usan APIs públicas
> documentadas por cada proveedor, sin ese problema. Más detalle en la
> sección [Sobre LinkedIn](#sobre-linkedin) más abajo.

## Qué necesitás

- Python 3.10+
- Tu CV en PDF (opcional, pero ayuda para el paso 2)
- [Claude Code](https://claude.com/claude-code) instalado — el flujo de
  abajo está pensado para usarlo, aunque también podés completar el config
  a mano sin él.

## Cómo correrlo (con Claude Code)

**1. Instalá las dependencias**

```bash
pip install -r requirements.txt
```

**2. Preparación de tu config**

Copiá `config.example.yaml` a `config.yaml` y poné tu CV en esta carpeta
(por ejemplo `mi_cv.pdf`).

Abrí esta carpeta con Claude Code (`claude` en la terminal, parado acá
adentro) y decile algo como:

> Leé mi CV en ./mi_cv.pdf y completá config.yaml:
> 1. Sugerime 15-20 empresas relevantes a mi perfil para la sección
>    sources.ats.companies (con sus slugs de Greenhouse/Ashby/Lever)
> 2. Armá scoring.stack_weights con las tecnologías/skills de mi CV,
>    pesando más lo que más me define
> 3. Ajustá filters.seniority, filters.location y filters.companies.banned
>    según lo que te diga sobre mi búsqueda (nivel, ubicación, exclusiones)
>
> Mi búsqueda es: [contame acá en una o dos líneas qué estás buscando —
> rol, modalidad, ubicación, lo que sea relevante]

Claude Code va a leer el PDF y editarte `config.yaml` directamente. **Revisalo
vos antes de correr nada** — es un punto de partida, no el resultado final.
Nadie conoce tu búsqueda mejor que vos.

**3. Corré el buscador**

```bash
python main.py
```

Esto va a:
1. Buscar en todas las fuentes que activaste (`enabled: true`)
2. Deduplicar y aplicar los filtros duros
3. Puntuar y ordenar lo que sobrevivió
4. Escribir el resultado en `resultados.md` (o `.csv`/`.json` según
   `output.format`)

**4. Rondas siguientes**

Si corrés esto de nuevo más adelante y no querés ver los mismos avisos:

```bash
python main.py --save-blacklist
```

Esto guarda las URLs del resultado actual en `blacklist.txt`, y la próxima
corrida las excluye automáticamente.

## Estructura del kit

```
job_scraper_kit/
├── config.example.yaml   # plantilla de config — copiar a config.yaml
├── main.py                # orquestador: junta fuentes, filtra, puntúa, escribe
├── filters.py              # filtros duros (seniority, ubicación, blacklist)
├── scoring.py               # scoring configurable por keywords y pesos
├── requirements.txt
└── sources/
    ├── ats.py                # Greenhouse / Ashby / Lever — PROBADO, estable
    ├── linkedin.py           # LinkedIn jobs-guest API — ver advertencia abajo
    └── regional.py           # GetOnBoard (probado) + stubs de otros portales
```

## Fuentes: qué está probado y qué no

| Fuente | Estado | Notas |
|---|---|---|
| Greenhouse / Ashby / Lever | ✅ Probado, estable | APIs públicas documentadas por cada proveedor. Sin riesgo de bloqueo. |
| LinkedIn (jobs-guest) | ⚠️ Funciona, pero fuera de ToS | Ver advertencia en `config.example.yaml` y abajo. |
| GetOnBoard | ✅ Probado, estable | API JSON pública, países LATAM. |
| Computrabajo / Bumeran / ZonaJobs / Trabajo.org | ❌ No implementado | Son SPAs — necesitan Playwright/Selenium para renderizar JS. Quedan como stubs documentados en `sources/regional.py`. |

### Sobre LinkedIn

El endpoint que usa `sources/linkedin.py` es el mismo que usan los buscadores
para indexar avisos públicos — no requiere login ni credenciales. Aun así,
el scraping automatizado de LinkedIn va contra sus Términos de Servicio.
En la práctica:

- LinkedIn puede banear temporalmente tu IP si hacés muchas requests seguidas
  (por eso `max_requests` y `delay_seconds` en la config — respetalos)
- El endpoint puede cambiar sin aviso
- Un problema real que tuvimos en la sesión original: el resumen de
  búsqueda de LinkedIn puede decir "remote" para un aviso que en realidad
  es híbrido o presencial. Si te importa la precisión, no confíes solo en
  el resultado de `main.py` — abrí cada URL final y fijate la descripción
  completa antes de aplicar. `filters.verify_remote_from_full_text()` está
  para automatizar ese segundo paso si querés (fetcheás cada URL, le pasás
  el texto, y te dice si el remote es real).

Dejalo en `enabled: false` en el config si preferís no correr ese riesgo —
con solo ATS + GetOnBoard ya tenés una base sólida y 100% legal.

## Cómo se define el score

`scoring.py` NO decide qué se descarta (eso lo hace `filters.py` antes) —
solo ordena lo que sobrevivió a los filtros. Cada aviso suma puntos por:

- Coincidencia de palabras de tu stack (`scoring.stack_weights`)
- Resta si aparece una tecnología que no querés (`scoring.negative_stack_weights`)
- Bonus si el título tiene una palabra de seniority que buscás
  (`scoring.title_bonus`)
- Bonus según qué tan bien matchea la ubicación
  (`scoring.location_bonus`: tu ciudad > país remoto > región remota > global remoto)

Todo eso es 100% editable en `config.yaml` — no hay nada hardcodeado en el
código, los pesos son datos, no lógica.

## Extender esto

- **Agregar un portal nuevo**: escribí una función en `sources/regional.py`
  que devuelva una lista de `RawJob` (mirá `fetch_getonboard` como ejemplo
  de una API JSON real). Si el portal es una SPA, vas a necesitar Playwright.
  Pedile a Claude Code que te lo escriba pasándole la URL de búsqueda del
  portal y un ejemplo de qué avisos esperás ver.
- **Cambiar la lógica de filtrado**: todo vive en `filters.py`, con
  regexes explícitas y comentadas — no hay nada oculto en una librería externa.
- **Cambiar el formato de salida**: agregá una función `write_<formato>` en
  `main.py` siguiendo el patrón de `write_markdown`/`write_csv`/`write_json`.

## Limitaciones conocidas

- El scoring y los filtros trabajan sobre título + descripción corta (lo que
  cada fuente devuelve de entrada) — no hacen fetch de la página completa de
  cada aviso salvo que uses `verify_remote_from_full_text` a mano. Eso
  significa que algunos avisos con descripción completa distinta al resumen
  pueden colarse o quedar afuera incorrectamente.
- `sources/regional.py` tiene 4 portales sin implementar — no son bugs,
  están documentados como tal.
- Los IDs numéricos de seniority/modality de GetOnBoard (`GOB_SENIORITY_JUNIOR_IDS`,
  `GOB_MODALITY_REMOTE_ID` en `sources/regional.py`) se dedujeron
  empíricamente probando avisos conocidos, no están documentados
  oficialmente por GetOnBoard — si notás resultados raros, es el primer
  lugar para revisar.
