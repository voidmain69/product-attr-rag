# product-attr-rag (`attrpipe`)

**Language / Мова:** [English](#english) · [Українська](#українська)

**Status:** `v1.0.0` — all architecture layers (docs 00–09) implemented · Python 3.12 · `mypy --strict` · CI green · 137 unit + 27 integration + 4 golden tests.

> **Fact-first pipeline that harvests product specifications from manufacturer
> websites and answers questions about them with exact, cited, dated facts.**
> A product attribute is a *structured fact, not text*: an exact lookup in the
> Canonical Fact Store is the primary answer route; vector search is only a
> fallback for rich content and fuzzy queries.

---

## English

### What it is

`attrpipe` is a data pipeline **and** a retrieval service. It crawls product
pages across heterogeneous sites (different CMSs, structures, anti-bot
protection), extracts specifications from both structured blocks and rich
content (prose, PDF, images), normalizes wildly different vendor taxonomies to
one canonical ontology, and stores every value as a versioned fact with full
provenance. On top of that store it answers natural-language questions with a
**fact-first RAG** router.

It is designed around one idea that ordinary "naive RAG" gets wrong for specs:
`"Weight: 2.3 kg"` chopped into a chunk retrieves the weight of *some* product,
not *the* product. So attrpipe resolves the product and the attribute first,
then does a deterministic lookup — and falls back to hybrid retrieval only when
that is impossible.

### Current state

Production-shaped and feature-complete against the design docs; released as
**v1.0.0** (tags `v0.1.0` → `v1.0.0`, each a `develop → main` merge). Everything
below is implemented and tested:

| Layer | What's live |
|---|---|
| **fetch** | static HTTP fetcher, robots.txt + Crawl-delay + per-domain rate limit, URL canonicalization |
| **extraction** | cost cascade Tier 1 JSON-LD · Tier 2 Shopify `.json` · Tier 3 DOM tables/`<dl>` · Tier 4 grounded LLM |
| **normalization** | canonical ontology, dictionary attribute mapping, unit conversion, conflict resolution, HITL learning loop |
| **storage** | append-only versioned fact store, Raw Store (MinIO), self-contained chunks (pgvector) |
| **rag** | route A exact lookup + route B hybrid retrieval, `compare`, `filter` — all cited |
| **hitl** | moderation queues for exceptions + resolve → dictionary learning |
| **quality/ops** | quality metrics + golden-set regression gate, Prometheus/Grafana telemetry |

The LLM tier and hybrid-generation use injectable interfaces (tested with fakes,
no network). For live Claude calls install the `llm` extra and set
`ANTHROPIC_API_KEY` (model `claude-opus-4-8`); a dependency-free `HashingEmbedder`
makes hybrid retrieval work out of the box.

### What it does

- **Crawl** — discovers product URLs (feeds/API → sitemap → listings), fetches
  static-first (headless only when needed), respects robots.txt / rate limits,
  and stores raw artifacts with fetch provenance.
- **Extract** — a cost cascade: Tier 1 structured data (JSON-LD, embedded JSON)
  → Tier 2 CMS adapters → Tier 3 DOM heuristics → Tier 4 LLM (rich text / PDF /
  vision). Each fact carries a verbatim `source_span` for grounding.
- **Normalize** — maps raw attribute names to a canonical, versioned ontology
  (dictionary → embedding → LLM judge → human-in-the-loop), converts values to
  canonical units, resolves the same product across sources (GTIN → MPN → brand
  + model → fuzzy), and resolves conflicting values explicitly.
- **Store** — an append-only, versioned Canonical Fact Store (Postgres) plus a
  hybrid index (pgvector dense + BM25 lexical) built from self-contained chunks.
- **Answer** — routes each query: exact fact lookup first (deterministic SQL via
  safe functions), hybrid retrieval as fallback, always with citations, dates,
  explicit conflicts, and an honest "unknown" when data is missing.

### What it lets you do

- Ask *"how much does Acme Model X weigh?"* and get **2.3 kg**, with a link to
  the manufacturer page and the date the fact was captured.
- **Compare** several products on the same attribute in correct, canonical units.
- **Filter** a catalogue by structured constraints (`ip_rating = IP67 AND
  net_weight < 300 g`) — something vector search does poorly and normalized SQL
  does easily.
- Trust the answers: every value is traceable to a source span, versioned
  ("as of a date"), and conflicts between sources are shown, not hidden.

### Who it is for

- **Product / catalogue teams & marketplaces** that need clean, comparable specs
  aggregated from many vendor sites.
- **Search / RAG engineers** who need attribute answers that are precise enough
  to compare and filter on, not approximate paragraph matches.
- **Data / ML engineers** building a provenance-first knowledge base of product
  facts with auditability and reproducibility.

### Architecture

```
Sitemaps/Feeds → Discovery → Fetcher pool → Raw Store (S3/MinIO)
      → Extraction (Tier 1 structured → Tier 2 CMS → Tier 3 DOM → Tier 4 LLM)
      → Normalization (ontology, units, entity resolution, conflicts)
      → Fact Store (Postgres, append-only) + Hybrid index (pgvector + BM25)
      → RAG (exact lookup → hybrid retrieval → generation with citations)
```

Package layout mirrors the layers: `attrpipe/{fetch,extraction,normalization,storage,rag,pipeline,quality,api,core}`.

### How it works

**Ingestion — one URL to persisted facts.** `IngestPipeline.ingest(url,
product_ref)` runs the whole flow synchronously:

1. `fetch` turns the URL into a `RawArtifact` (browser-like headers, robots
   check, content hash) — respecting per-domain rate limits.
2. the artifact is written to the **Raw Store** *before* extraction, so
   re-extraction is reproducible and never re-hits the site (idempotency).
3. every extractor in the cost cascade runs on the artifact; each emits
   `CandidateFact`s with a verbatim `source_span`. The LLM tier drops any fact
   whose value isn't grounded in its span (anti-hallucination).
4. `normalization` maps each `raw_attribute → attribute_key` (dictionary,
   seeded by confirmed HITL mappings), converts the value to the canonical unit,
   and rejects out-of-range anomalies — routing unmapped/anomalous candidates to
   a HITL queue instead of guessing.
5. products are resolved to one `product_id` (GTIN > MPN+brand > brand+model);
   facts are written **append-only** — a new value supersedes the old, or, across
   sources, `ConflictResolver` picks the effective value by authority/freshness/
   confidence and flags `disputed` when equal-authority sources disagree.
6. a **self-contained chunk** (product header + facts + source line) is embedded
   and indexed for hybrid retrieval.

**Answering — fact-first routing.** `POST /v1/answer` resolves the product and
the requested attribute, then:

- **Route A (exact lookup):** if both are known and a fact exists, return the
  canonical value verbatim with its citation and date — no LLM, no guessing.
- **Route B (hybrid retrieval):** for fuzzy / rich-content questions, dense
  search over self-contained chunks returns grounded evidence with its source.
- Otherwise an explicit **"unknown"** — the layer never fabricates a value.

```
"what is the net weight?"        → route A → net weight: 2300.0 g. Source: vendor.com, as of 2026-07-10.
"is it waterproof for the rain?" → route B → grounded chunk evidence + source
"what is the weight?" (no match) → refused → honest unknown
```

Everything is deterministic and provenance-carrying; the only non-deterministic
piece is the optional Tier-4 LLM, isolated behind an interface.

### Service API

The answering service (`attrpipe.api`) exposes the API below (design per
[docs/05](docs/05-rag-pipeline.md)) — all routes are **live** (run
`python tools/dev.py serve`; interactive docs at `/docs`).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/v1/products/{product_id}` | Resolved product entity: brand, model, category, identifiers, source URLs. |
| `GET` | `/v1/products/{product_id}/facts` | All effective canonical facts for a product (versioned, with provenance). |
| `GET` | `/v1/products/{product_id}/facts/{attribute_key}` | A single attribute value with provenance + date, or an honest 404. |
| `POST` | `/v1/answer` | Answer a natural-language question; fact-first routing — exact lookup (route A) or hybrid retrieval (route B) — with citation, or an honest "unknown". |
| `POST` | `/v1/compare` | Compare one or more attributes across several products; a table in canonical units. |
| `POST` | `/v1/filter` | Products matching structured attribute constraints (e.g. `ip_rating=IP67 AND net_weight<300`). |
| `GET` | `/v1/attributes` | Canonical attribute ontology: categories, data types, units, synonyms. |
| `GET` | `/v1/hitl` · `/v1/hitl/{queue}` | Human-in-the-loop moderation queues + counts (docs/06). |
| `POST` | `/v1/hitl/{item_id}/resolve` | Resolve a queued exception; confirmed attribute mappings feed the dictionary. |
| `GET` | `/healthz` · `/metrics` | Liveness probe and Prometheus metrics (see [docs/08](docs/08-telemetry-standards.md)). |

Example — ask a question once the service is running:

```bash
curl -s localhost:8010/v1/answer -H 'content-type: application/json' \
  -d '{"question": "what is the net weight?", "brand": "Acme", "model": "Model X"}'
# → {"found": true, "route": "exact_lookup", "answer": "net weight: 2300.0 g. Source: ...",
#    "canonical_value": 2300.0, "canonical_unit": "g", "citation": {...}}
```

### Quick start

Requires: Python 3.12+, Docker.

```bash
python tools/dev.py bootstrap   # venv + deps + pre-commit
python tools/dev.py up          # Postgres+pgvector, RabbitMQ, MinIO, Prometheus, Grafana
python tools/dev.py check       # lint + typecheck + unit tests + golden gate
python tools/dev.py serve       # run the API on http://localhost:8010 (docs at /docs)
```

`dev.py` commands: `bootstrap` · `check` · `fix` · `lint` · `typecheck` ·
`test` · `test-all` (incl. integration) · `golden` · `cov` · `serve` · `up` ·
`up-all` (+OpenSearch) · `down` · `status` · `psql`.

Local services after `up`:

| Service | URL | Purpose |
|---|---|---|
| API | http://localhost:8010 | answering service (`serve`; Swagger at `/docs`) |
| Postgres | `localhost:5432` | Canonical Fact Store + pgvector (schema: `infra/postgres/init/`) |
| RabbitMQ UI | http://localhost:15672 | queues between layers |
| MinIO Console | http://localhost:9001 | Raw Store (raw artifacts) |
| Prometheus | http://localhost:9090 | metrics |
| Grafana | http://localhost:3000 | dashboards |
| OpenSearch | `localhost:9200` | BM25 (profile `search`: `dev.py up-all`) |

Optional — enable live Tier-4 LLM extraction / generation:

```bash
pip install -e '.[llm]'          # anthropic SDK
export ANTHROPIC_API_KEY=...     # model: claude-opus-4-8
```

### Testing

- **unit** — fast, no infra: `python tools/dev.py test`.
- **integration** — against the docker-compose stack: `python tools/dev.py test-all`.
- **golden** — deterministic regression gate over curated fixtures (release gate
  for extraction/normalization/rag changes): `python tools/dev.py golden`.

CI runs lint, format, `mypy --strict`, unit tests + coverage, and the golden gate
on every PR. Integration tests need the DB and run locally.

### Documentation

| Doc | Topic |
|---|---|
| [00](docs/00-architecture-overview.md) | Architecture overview and principles |
| [01](docs/01-crawling.md) | Crawling: discovery, fetchers, anti-bot, legality |
| [02](docs/02-extraction.md) | Tier 1–4 extraction cascade, anti-hallucination grounding |
| [03](docs/03-normalization-taxonomy.md) | Ontology, taxonomy mapping, entity resolution |
| [04](docs/04-storage-indexing.md) | Fact store, versioning, chunking, hybrid indexes |
| [05](docs/05-rag-pipeline.md) | Fact-first answer routing, citations |
| [06](docs/06-quality-operations.md) | Quality metrics, golden set, drift, HITL |
| [07](docs/07-tech-stack-infrastructure.md) | Stack, queues, scaling, cost |
| [08](docs/08-telemetry-standards.md) | Telemetry & monitoring standards |
| [09](docs/09-testing-requirements.md) | Testing requirements |

### Development

- Project rules, code style, git flow: [CLAUDE.md](CLAUDE.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
- Branches: work flows through `develop` (PRs from `feature/*`); releases are `develop → main` PRs with a tag.
- Before committing: `python tools/dev.py check`.

### License

MIT — see [LICENSE](LICENSE).

---

## Українська

**Статус:** `v1.0.0` — усі шари архітектури (docs 00–09) реалізовані · Python 3.12 · `mypy --strict` · CI зелений · 137 unit + 27 integration + 4 golden тести.

> **Fact-first пайплайн, що здобуває характеристики товарів із сайтів
> виробників і відповідає на запитання про них точними, датованими фактами з
> цитатами.** Характеристика товару — це *структурований факт, а не текст*:
> точний lookup у Canonical Fact Store — головний маршрут відповіді, а
> векторний пошук лише fallback для rich-контенту й нечітких запитів.

### Що це

`attrpipe` — це водночас **пайплайн даних** і **сервіс відповідей**. Він краулить
сторінки товарів на різнорідних сайтах (різні CMS, структури, антибот-захист),
витягує характеристики і зі структурованих блоків, і з rich-контенту (проза,
PDF, зображення), нормалізує геть різні таксономії виробників до єдиної
канонічної онтології та зберігає кожне значення як версіонований факт з повним
провенансом. Поверх цього сховища він відповідає на запити природною мовою через
**fact-first RAG**.

Він побудований навколо ідеї, яку звичайний «naive RAG» на характеристиках
провалює: рядок `«Вага: 2.3 кг»`, нарізаний у чанк, знаходить вагу *якогось*
товару, а не *потрібного*. Тому attrpipe спершу розв'язує товар і атрибут, потім
робить детермінований lookup — і переходить до гібридного пошуку лише коли це
неможливо.

### Поточний стан

Готовий за дизайн-документами й випущений як **v1.0.0** (теги `v0.1.0` →
`v1.0.0`, кожен — merge `develop → main`). Усе нижче реалізовано й покрито
тестами:

| Шар | Що працює |
|---|---|
| **fetch** | статичний HTTP-фетчер, robots.txt + Crawl-delay + per-domain rate limit, канонізація URL |
| **extraction** | каскад Tier 1 JSON-LD · Tier 2 Shopify `.json` · Tier 3 DOM таблиці/`<dl>` · Tier 4 grounded LLM |
| **normalization** | канонічна онтологія, словниковий мапінг атрибутів, конверсія одиниць, conflict resolution, HITL навчальний цикл |
| **storage** | append-only версіонований fact store, Raw Store (MinIO), самодостатні чанки (pgvector) |
| **rag** | route A exact lookup + route B hybrid retrieval, `compare`, `filter` — усе з цитатами |
| **hitl** | черги модерації винятків + resolve → навчання словника |
| **quality/ops** | метрики якості + golden-set регресійний гейт, телеметрія Prometheus/Grafana |

LLM-tier і hybrid-генерація — через ін'єктовані інтерфейси (тести на фейках, без
мережі). Для живих Claude-викликів: extra `llm` + `ANTHROPIC_API_KEY` (модель
`claude-opus-4-8`); дефолтний `HashingEmbedder` (без залежностей) робить hybrid
retrieval робочим одразу.

### Що він робить

- **Crawl** — знаходить URL товарів (фіди/API → sitemap → лістинги), фетчить
  static-first (headless лише за потреби), поважає robots.txt / rate limits і
  зберігає сирі артефакти з провенансом фетчу.
- **Extract** — каскад за вартістю: Tier 1 структуровані дані (JSON-LD,
  вбудований JSON) → Tier 2 CMS-адаптери → Tier 3 DOM-евристики → Tier 4 LLM
  (rich text / PDF / vision). Кожен факт несе дослівний `source_span` для
  grounding.
- **Normalize** — мапить сирі назви атрибутів на канонічну версіоновану
  онтологію (словник → embedding → LLM-суддя → human-in-the-loop), конвертує
  значення в канонічні одиниці, зводить той самий товар з різних джерел (GTIN →
  MPN → бренд+модель → fuzzy) та явно вирішує конфлікти значень.
- **Store** — append-only версіоноване Canonical Fact Store (Postgres) плюс
  гібридний індекс (pgvector dense + BM25 lexical) із самодостатніх чанків.
- **Answer** — маршрутизує запит: спершу точний fact lookup (детермінований SQL
  через безпечні функції), гібридний пошук як fallback, завжди з цитатами,
  датами, явними конфліктами і чесним «невідомо», коли даних немає.

### Що він дозволяє

- Спитати *«скільки важить Acme Model X?»* і отримати **2.3 кг** з посиланням на
  сторінку виробника і датою фіксації факту.
- **Порівнювати** кілька товарів за одним атрибутом у коректних канонічних
  одиницях.
- **Фільтрувати** каталог за структурованими умовами (`ip_rating = IP67 AND
  net_weight < 300 g`) — те, що векторний пошук робить погано, а нормалізований
  SQL — легко.
- Довіряти відповідям: кожне значення простежуване до source span,
  версіоноване («станом на дату»), а конфлікти між джерелами показані, а не
  приховані.

### Для кого

- **Продуктові / каталожні команди й маркетплейси**, яким потрібні чисті,
  порівнювані характеристики, зібрані з багатьох сайтів виробників.
- **Search / RAG інженери**, яким потрібні відповіді про атрибути, достатньо
  точні для порівняння й фільтрації, а не приблизні збіги абзаців.
- **Data / ML інженери**, що будують provenance-first базу знань про факти
  товарів з аудитом і відтворюваністю.

### Архітектура

```
Sitemaps/Feeds → Discovery → Fetcher pool → Raw Store (S3/MinIO)
      → Extraction (Tier 1 structured → Tier 2 CMS → Tier 3 DOM → Tier 4 LLM)
      → Normalization (онтологія, одиниці, entity resolution, конфлікти)
      → Fact Store (Postgres, append-only) + Hybrid index (pgvector + BM25)
      → RAG (exact lookup → hybrid retrieval → generation з citations)
```

Структура пакета 1:1 з шарами: `attrpipe/{fetch,extraction,normalization,storage,rag,pipeline,quality,api,core}`.

### Як це працює

**Інжест — від URL до збережених фактів.** `IngestPipeline.ingest(url,
product_ref)` виконує весь потік синхронно:

1. `fetch` перетворює URL на `RawArtifact` (браузероподібні заголовки,
   перевірка robots, content hash) — з дотриманням per-domain rate limit.
2. артефакт пишеться в **Raw Store** *до* екстракції, тож реекстракція
   відтворювана й ніколи не б'є в сайт повторно (ідемпотентність).
3. кожен екстрактор каскаду обробляє артефакт і видає `CandidateFact` з
   дослівним `source_span`. LLM-tier відкидає факт, чиє значення не grounded у
   span (анти-галюцинація).
4. `normalization` мапить `raw_attribute → attribute_key` (словник, засіяний
   підтвердженими HITL-мапінгами), конвертує значення в канонічну одиницю й
   відсіює аномалії поза межами — unmapped/аномальні йдуть у HITL-чергу, а не
   вгадуються.
5. товари зводяться до одного `product_id` (GTIN > MPN+brand > brand+model);
   факти пишуться **append-only** — нове значення супресідить старе, а між
   джерелами `ConflictResolver` обирає діюче за авторитетністю/свіжістю/
   confidence і ставить `disputed` при незгоді рівноавторитетних джерел.
6. **самодостатній чанк** (шапка товару + факти + рядок джерела) embed-иться
   й індексується для hybrid retrieval.

**Відповідь — fact-first маршрутизація.** `POST /v1/answer` розв'язує товар і
запитуваний атрибут, потім:

- **Route A (exact lookup):** якщо обидва відомі й факт є — повертає канонічне
  значення дослівно з цитатою й датою — без LLM, без вгадування.
- **Route B (hybrid retrieval):** для нечітких/rich-запитів dense-пошук по
  самодостатніх чанках повертає grounded-evidence з джерелом.
- Інакше — явне **«невідомо»**; шар ніколи не вигадує значення.

```
«what is the net weight?»        → route A → net weight: 2300.0 g. Source: vendor.com, as of 2026-07-10.
«is it waterproof for the rain?» → route B → grounded-чанк + джерело
«what is the weight?» (нема)      → refused → чесне «невідомо»
```

Усе детерміноване й з провенансом; єдиний недетермінований елемент — опційний
Tier-4 LLM, ізольований за інтерфейсом.

### API сервісу

Сервіс відповідей (`attrpipe.api`) надає API нижче (дизайн за
[docs/05](docs/05-rag-pipeline.md)) — усі маршрути **вже працюють** (`python
tools/dev.py serve`; інтерактивні docs на `/docs`).

| Метод | Ендпоінт | Опис |
|---|---|---|
| `GET` | `/v1/products/{product_id}` | Розв'язана сутність товару: бренд, модель, категорія, ідентифікатори, URL-джерела. |
| `GET` | `/v1/products/{product_id}/facts` | Усі діючі канонічні факти товару (версіоновані, з провенансом). |
| `GET` | `/v1/products/{product_id}/facts/{attribute_key}` | Значення одного атрибута з провенансом і датою, або чесний 404. |
| `POST` | `/v1/answer` | Відповідь природною мовою; fact-first маршрутизація — exact lookup (route A) або hybrid retrieval (route B) — з цитатою, або чесне «невідомо». |
| `POST` | `/v1/compare` | Порівняння атрибутів кількох товарів; таблиця в канонічних одиницях. |
| `POST` | `/v1/filter` | Товари за структурованими умовами атрибутів (напр. `ip_rating=IP67 AND net_weight<300`). |
| `GET` | `/v1/attributes` | Канонічна онтологія атрибутів: категорії, типи даних, одиниці, синоніми. |
| `GET` | `/v1/hitl` · `/v1/hitl/{queue}` | Черги human-in-the-loop модерації + лічильники (docs/06). |
| `POST` | `/v1/hitl/{item_id}/resolve` | Резолв винятку з черги; підтверджені мапінги атрибутів ідуть у словник. |
| `GET` | `/healthz` · `/metrics` | Проба liveness та метрики Prometheus (див. [docs/08](docs/08-telemetry-standards.md)). |

Приклад — запит, коли сервіс запущено:

```bash
curl -s localhost:8010/v1/answer -H 'content-type: application/json' \
  -d '{"question": "what is the net weight?", "brand": "Acme", "model": "Model X"}'
# → {"found": true, "route": "exact_lookup", "answer": "net weight: 2300.0 g. Source: ...",
#    "canonical_value": 2300.0, "canonical_unit": "g", "citation": {...}}
```

### Швидкий старт

Потрібні: Python 3.12+, Docker.

```bash
python tools/dev.py bootstrap   # venv + залежності + pre-commit
python tools/dev.py up          # Postgres+pgvector, RabbitMQ, MinIO, Prometheus, Grafana
python tools/dev.py check       # lint + typecheck + unit-тести + golden-гейт
python tools/dev.py serve       # API на http://localhost:8010 (docs на /docs)
```

Команди `dev.py`: `bootstrap` · `check` · `fix` · `lint` · `typecheck` · `test` ·
`test-all` (з integration) · `golden` · `cov` · `serve` · `up` · `up-all`
(+OpenSearch) · `down` · `status` · `psql`.

Локальні сервіси після `up`:

| Сервіс | URL | Призначення |
|---|---|---|
| API | http://localhost:8010 | сервіс відповідей (`serve`; Swagger на `/docs`) |
| Postgres | `localhost:5432` | Canonical Fact Store + pgvector (схема: `infra/postgres/init/`) |
| RabbitMQ UI | http://localhost:15672 | черги між шарами |
| MinIO Console | http://localhost:9001 | Raw Store (сирі артефакти) |
| Prometheus | http://localhost:9090 | метрики |
| Grafana | http://localhost:3000 | дашборди |
| OpenSearch | `localhost:9200` | BM25 (профіль `search`: `dev.py up-all`) |

Опційно — увімкнути живу Tier-4 LLM-екстракцію / генерацію:

```bash
pip install -e '.[llm]'          # anthropic SDK
export ANTHROPIC_API_KEY=...     # модель: claude-opus-4-8
```

### Тестування

- **unit** — швидко, без інфри: `python tools/dev.py test`.
- **integration** — проти docker-compose стеку: `python tools/dev.py test-all`.
- **golden** — детермінований регресійний гейт по курованих фікстурах (реліз-гейт
  для змін extraction/normalization/rag): `python tools/dev.py golden`.

CI на кожному PR: lint, format, `mypy --strict`, unit + coverage, golden-гейт.
Integration потребують БД і гоняться локально.

### Документація

| Doc | Тема |
|---|---|
| [00](docs/00-architecture-overview.md) | Огляд архітектури і принципи |
| [01](docs/01-crawling.md) | Crawling: discovery, fetcher-и, антибот, легальність |
| [02](docs/02-extraction.md) | Каскад екстракції Tier 1–4, анти-галюцинаційний grounding |
| [03](docs/03-normalization-taxonomy.md) | Онтологія, мапінг таксономій, entity resolution |
| [04](docs/04-storage-indexing.md) | Fact store, версіонування, чанкінг, гібридні індекси |
| [05](docs/05-rag-pipeline.md) | Fact-first маршрутизація відповіді, citations |
| [06](docs/06-quality-operations.md) | Метрики якості, golden set, drift, HITL |
| [07](docs/07-tech-stack-infrastructure.md) | Стек, черги, масштабування, вартість |
| [08](docs/08-telemetry-standards.md) | Стандарти телеметрії та моніторингу |
| [09](docs/09-testing-requirements.md) | Вимоги до тестування |

### Розробка

- Правила проєкту, код-стайл, git-процес: [CLAUDE.md](CLAUDE.md) та [CONTRIBUTING.md](CONTRIBUTING.md).
- Гілки: робота йде через `develop` (PR з `feature/*`), релізи — PR `develop → main` з тегом.
- Перед комітом: `python tools/dev.py check`.

### Ліцензія

MIT — див. [LICENSE](LICENSE).
