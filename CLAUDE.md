# CLAUDE.md — attrpipe (product-attr-rag)

Fact-first пайплайн здобування характеристик товарів: crawl → extraction → normalization → storage → RAG.
Повна архітектура — у [docs/](docs/), починати з `docs/00-architecture-overview.md`.

## 1. Що це за проєкт

- **Характеристика товару — структурований факт, а не текст.** Точний lookup у Canonical Fact Store — головний маршрут відповіді; вектори — fallback.
- Пакет: `attrpipe` (`src/attrpipe/`), Python 3.12. Шари пакета 1:1 мапляться на документи `docs/01..05`.
- Інфраструктура локально: `docker-compose.yml` (Postgres+pgvector, RabbitMQ, MinIO, OpenSearch, Prometheus, Grafana). Схема БД: `infra/postgres/init/001_schema.sql`.

## 2. Незмінні архітектурні принципи

Порушення будь-якого з цих принципів — блокер на ревью:

1. **Провенанс усюди.** Жоден факт не існує без `source_url`, `fetched_at`, `extraction_method`, `source_span`, `confidence`.
2. **Каскад за вартістю.** Дешеві детерміновані методи завжди перед дорогими: static HTTP перед headless, Tier 1–3 перед LLM. Новий код не має права викликати LLM/браузер там, де є детермінований шлях.
3. **Ідемпотентність.** Повторна обробка того самого входу (той самий raw + та сама версія методу) дає той самий результат. Екстракція читає тільки з Raw Store, ніколи з живого сайту.
4. **Версіонування, не перезапис.** Факти append-only (`valid_from` / `superseded_by`). Онтологія версіонована. Міграції БД — тільки новими файлами в `infra/postgres/init/`, існуючі не редагуються.
5. **Politeness і легальність.** robots.txt, Crawl-delay, per-domain rate limits — не опції. Реєстр джерел (`sources`) з правовим статусом підтримується актуальним.
6. **Чесне "невідомо".** RAG-шар ніколи не вигадує значення; відсутність даних — явна відповідь.

## 3. Код-стайл

- **Python 3.12**, повна типізація. `mypy --strict` і `ruff` (конфіг у `pyproject.toml`) мають проходити без винятків; `# type: ignore` — тільки з кодом помилки і причиною поруч.
- Форматування — `ruff format`; лінт — `ruff check` (E,W,F,I,N,UP,B,C4,SIM,RUF,PL,T20). Рядок ≤ 100 символів.
- Іменування: модулі/функції `snake_case`, класи `PascalCase`, константи `UPPER_SNAKE`. Доменні терміни — як у docs: `candidate_fact`, `canonical_fact`, `attribute_key`, `raw_artifact_id`, `extraction_tier`.
- Моделі даних — Pydantic v2 (`attrpipe.domain`). Міжшаровий контракт змінюється тільки разом з оновленням відповідного документа в `docs/`.
- Логи — тільки structured через `attrpipe.core.logging` (structlog, JSON). `print` заборонений у `src/` (лінт T20).
- Помилки: не ковтати винятки; ретраї з backoff — на рівні черг/фетчерів, не розкидані по коду.
- Docstring кожного публічного модуля пояснює його роль і посилається на відповідний doc (`docs/NN-...`).
- Коментарі — тільки там, де код не може сказати сам (обмеження, неочевидні інваріанти). Без коментарів-переказів коду.

## 4. Git-процес

Гілки:
- `main` — релізна, захищена. Прямі пуші заборонені.
- `develop` — інтеграційна, дефолтна. Уся робота вливається сюди через PR.
- `feature/<slug>`, `fix/<slug>`, `chore/<slug>` — робочі гілки від `develop`.

Потік: `feature/*` → PR у `develop` (squash merge) → релізний PR `develop` → `main` (merge commit, тег `vX.Y.Z`).

Коміти — **Conventional Commits**: `type(scope): summary`.
Типи: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`. Scope = шар (`fetch`, `extraction`, `normalization`, `storage`, `rag`, `infra`, `core`).
Приклад: `feat(extraction): add Shopify .json adapter (Tier 2)`.

Перед комітом обов'язково: `python tools/dev.py check` (ruff + mypy + pytest) — зелене. Хуки не обходити (`--no-verify` заборонено).

Детальніше: [CONTRIBUTING.md](CONTRIBUTING.md).

## 5. Принципи розробки та узгодження коду

- **Малі PR по одному шару.** Один PR = одна зміна одного шару пайплайну. Зміна міжшарового контракту — окремий PR з оновленням docs.
- **Тести разом з кодом.** PR без тестів на нову логіку не приймається (вимоги: `docs/09-testing-requirements.md`).
- **Регресія на golden set** обов'язкова для змін у extraction/normalization/rag (парсери, промпти, онтологія, embedding-модель). Падіння метрик = блокер.
- Ревью дивиться в такому порядку: (1) не порушені принципи з §2 → (2) коректність і крайові кейси → (3) тести → (4) стиль. Стильові правки, які ловить лінтер, у ревью не обговорюються — їх ловить CI.
- Автоматичне ревью: кожен PR проходить CI (ruff, mypy, pytest). Claude code review (`.github/workflows/claude-review.yml`) — **опційний, вимкнений за замовчуванням**: запускається лише на вимогу (мітка `claude-review` на PR або ручний запуск workflow). Людина мержить після зеленого CI.

## 6. Робота Claude в цьому репо (автономний режим)

- Працюй самостійно: читай docs, приймай очевидні інженерні рішення сам, не питай підтвердження на кожен крок. Питання до людини — тільки при зміні міжшарового контракту, онтології, легальної політики краулінгу або видаленні даних.
- Після будь-якої зміни коду прожени `python tools/dev.py check`; лагодь усе, що впало, перш ніж звітувати.
- Нову роботу починай з гілки від `develop`; ніколи не коміть у `main`.
- Секрети (`.env`, ключі, проксі) не читати в логи, не комітити, не вставляти у відповіді.
- Живі сайти не краулити в тестах і при дебагу — використовувати фікстури з `tests/fixtures/`.

## 7. Ключові команди

```bash
python tools/dev.py bootstrap   # venv + залежності + pre-commit
python tools/dev.py check       # ruff + format-check + mypy + pytest
python tools/dev.py fix         # автофікс лінту + формат
python tools/dev.py test        # pytest (unit)
python tools/dev.py up          # docker compose: core + monitoring
python tools/dev.py down        # зупинити інфраструктуру
python tools/dev.py status      # стан контейнерів і healthchecks
```

## 8. Телеметрія і тестування

- Стандарти телеметрії (метрики, логи, трейси, алерти): `docs/08-telemetry-standards.md`.
- Вимоги до тестування (піраміда, golden set, coverage ≥ 80%): `docs/09-testing-requirements.md`.
