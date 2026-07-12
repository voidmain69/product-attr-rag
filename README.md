# product-attr-rag (`attrpipe`)

**Language / Мова:** [English](#english) · [Українська](#українська)

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

### Service API (target design)

The answering service (`attrpipe.api`) exposes the API below (design per
[docs/05](docs/05-rag-pipeline.md)). The exact-lookup MVP is **live** (run
`python tools/dev.py serve`); `POST` answer/compare/filter routes are the next
increment. Status: ✅ live · 🚧 planned.

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `GET` | `/v1/products/{product_id}` | ✅ | Resolved product entity: brand, model, category, identifiers, source URLs. |
| `GET` | `/v1/products/{product_id}/facts` | ✅ | All effective canonical facts for a product (versioned, with provenance). |
| `GET` | `/v1/products/{product_id}/facts/{attribute_key}` | ✅ | A single attribute value with provenance + date, or an honest 404. |
| `GET` | `/v1/attributes` | ✅ | Canonical attribute ontology: categories, data types, units, synonyms. |
| `GET` | `/healthz` | ✅ | Liveness / readiness probe. |
| `GET` | `/metrics` | ✅ | Prometheus metrics (see [docs/08](docs/08-telemetry-standards.md)). |
| `POST` | `/v1/answer` | 🚧 | Answer a natural-language question about a product attribute; fact-first routing, returns value + unit + citation + date, or an honest "unknown". |
| `POST` | `/v1/compare` | 🚧 | Compare one or more attributes across several products; returns a table in canonical units. |
| `POST` | `/v1/filter` | 🚧 | Return products matching structured attribute constraints (e.g. `ip_rating=IP67 AND net_weight<300`). |
| `GET` | `/healthz` | Liveness / readiness probe. |
| `GET` | `/metrics` | Prometheus metrics (see [docs/08](docs/08-telemetry-standards.md)). |

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

### Quick start

Requires: Python 3.12+, Docker.

```bash
python tools/dev.py bootstrap   # venv + deps + pre-commit
python tools/dev.py up          # Postgres+pgvector, RabbitMQ, MinIO, Prometheus, Grafana
python tools/dev.py check       # lint + typecheck + tests
```

Local services after `up`:

| Service | URL | Purpose |
|---|---|---|
| Postgres | `localhost:5432` | Canonical Fact Store (schema: `infra/postgres/init/`) |
| RabbitMQ UI | http://localhost:15672 | queues between layers |
| MinIO Console | http://localhost:9001 | Raw Store (raw artifacts) |
| Prometheus | http://localhost:9090 | metrics |
| Grafana | http://localhost:3000 | dashboards |
| OpenSearch | `localhost:9200` | BM25 (profile `search`: `dev.py up-all`) |

### Development

- Project rules, code style, git flow: [CLAUDE.md](CLAUDE.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
- Branches: work flows through `develop` (PRs from `feature/*`); releases are `develop → main` PRs.
- Before committing: `python tools/dev.py check`.

### License

MIT — see [LICENSE](LICENSE).

---

## Українська

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

### API сервісу (цільовий дизайн)

Сервіс відповідей (`attrpipe.api`) надає API нижче (дизайн за
[docs/05](docs/05-rag-pipeline.md)). Exact-lookup MVP **вже працює** (`python
tools/dev.py serve`); `POST` answer/compare/filter — наступний інкремент.
Статус: ✅ живе · 🚧 заплановано.

| Метод | Ендпоінт | Статус | Опис |
|---|---|---|---|
| `GET` | `/v1/products/{product_id}` | ✅ | Розв'язана сутність товару: бренд, модель, категорія, ідентифікатори, URL-джерела. |
| `GET` | `/v1/products/{product_id}/facts` | ✅ | Усі діючі канонічні факти товару (версіоновані, з провенансом). |
| `GET` | `/v1/products/{product_id}/facts/{attribute_key}` | ✅ | Значення одного атрибута з провенансом і датою, або чесний 404. |
| `GET` | `/v1/attributes` | ✅ | Канонічна онтологія атрибутів: категорії, типи даних, одиниці, синоніми. |
| `GET` | `/healthz` | ✅ | Проба liveness / readiness. |
| `GET` | `/metrics` | ✅ | Метрики Prometheus (див. [docs/08](docs/08-telemetry-standards.md)). |
| `POST` | `/v1/answer` | 🚧 | Відповідь на запит природною мовою про характеристику; fact-first маршрутизація, повертає значення + одиницю + цитату + дату, або чесне «невідомо». |
| `POST` | `/v1/compare` | 🚧 | Порівняння одного чи кількох атрибутів для кількох товарів; повертає таблицю в канонічних одиницях. |
| `POST` | `/v1/filter` | 🚧 | Повертає товари за структурованими умовами атрибутів (напр. `ip_rating=IP67 AND net_weight<300`). |

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

### Швидкий старт

Потрібні: Python 3.12+, Docker.

```bash
python tools/dev.py bootstrap   # venv + залежності + pre-commit
python tools/dev.py up          # Postgres+pgvector, RabbitMQ, MinIO, Prometheus, Grafana
python tools/dev.py check       # lint + typecheck + tests
```

Локальні сервіси після `up`:

| Сервіс | URL | Призначення |
|---|---|---|
| Postgres | `localhost:5432` | Canonical Fact Store (схема: `infra/postgres/init/`) |
| RabbitMQ UI | http://localhost:15672 | черги між шарами |
| MinIO Console | http://localhost:9001 | Raw Store (сирі артефакти) |
| Prometheus | http://localhost:9090 | метрики |
| Grafana | http://localhost:3000 | дашборди |
| OpenSearch | `localhost:9200` | BM25 (профіль `search`: `dev.py up-all`) |

### Розробка

- Правила проєкту, код-стайл, git-процес: [CLAUDE.md](CLAUDE.md) та [CONTRIBUTING.md](CONTRIBUTING.md).
- Гілки: робота йде через `develop` (PR з `feature/*`), релізи — PR `develop → main`.
- Перед комітом: `python tools/dev.py check`.

### Ліцензія

MIT — див. [LICENSE](LICENSE).
