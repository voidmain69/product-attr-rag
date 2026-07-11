# product-attr-rag (attrpipe)

Fact-first пайплайн здобування характеристик товарів з сайтів виробників для точного RAG:
**crawl → extraction → normalization → storage → answering**.

> Характеристика товару — це структурований факт, а не текст. Точний lookup у Canonical Fact Store —
> головний маршрут відповіді; векторний пошук — fallback для rich-контенту й нечітких запитів.

## Архітектура

```
Sitemaps/Feeds → Discovery → Fetcher pool → Raw Store (S3)
      → Extraction (Tier 1 structured → Tier 2 CMS → Tier 3 DOM → Tier 4 LLM)
      → Normalization (онтологія, одиниці, entity resolution, конфлікти)
      → Fact Store (Postgres, append-only) + Hybrid index (pgvector + BM25)
      → RAG (exact lookup → hybrid retrieval → generation з citations)
```

Повна документація — у [docs/](docs/):

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

## Швидкий старт

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

## Розробка

- Правила проєкту, код-стайл, git-процес: [CLAUDE.md](CLAUDE.md) та [CONTRIBUTING.md](CONTRIBUTING.md).
- Гілки: робота йде через `develop` (PR з `feature/*`), релізи — PR `develop → main`.
- Перед комітом: `python tools/dev.py check`.

## Ліцензія

MIT — див. [LICENSE](LICENSE).
