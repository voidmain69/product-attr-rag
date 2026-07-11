# 08. Telemetry Standards: метрики, логи, трейси, алерти

Стандарти спостережуваності для всіх сервісів пайплайну. Реалізують вимоги `06-quality-operations.md` (розділ 6) конкретними інструментами й конвенціями. Порушення цих конвенцій — блокер на ревью: неспостережуваний воркер не деплоїться.

## 1. Стек моніторингу

| Сигнал | Інструмент | Де |
|---|---|---|
| Метрики | Prometheus (`prometheus-client`, endpoint `/metrics`) | `docker-compose --profile monitoring`, порт 9090 |
| Дашборди | Grafana (provisioning з `infra/grafana/`) | порт 3000 |
| Логи | structlog → JSON у stdout; агрегація Loki/ELK у проді | `attrpipe.core.logging` |
| Трейси | OpenTelemetry SDK → OTLP collector → Tempo/Jaeger | env `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Помилки | Sentry (проді); DSN через секрет-менеджер | опційно |

Локально Prometheus скрейпить воркери на портах 8001–8010 (див. `infra/prometheus/prometheus.yml`).

## 2. Конвенції метрик

Іменування: `attrpipe_<layer>_<name>_<unit>`, лейбли — тільки з обмеженою кардинальністю (`domain`, `tier`, `queue`, `route`; **ніколи** URL чи product_id).

Обов'язкові метрики по шарах (мапляться на метрики якості з `06 §1`):

**Кожен воркер (базовий набір):**
- `attrpipe_<layer>_processed_total{status="ok|error|skipped"}` — counter
- `attrpipe_<layer>_duration_seconds` — histogram
- `attrpipe_<layer>_queue_depth` — gauge (глибина вхідної черги)

**Crawling:**
- `attrpipe_fetch_requests_total{domain, render_mode, status_class}`
- `attrpipe_fetch_blocked_total{domain, reason="403|429|captcha"}`
- `attrpipe_fetch_freshness_age_seconds` — histogram віку останнього fetch

**Extraction:**
- `attrpipe_extraction_facts_total{tier}` — розподіл по tier-ах (частка дорогого Tier 4 — ключовий cost-індикатор)
- `attrpipe_extraction_grounding_pass_ratio` — gauge, частка LLM-фактів зі span-верифікацією
- `attrpipe_extraction_llm_tokens_total{direction="in|out"}` — вартість

**Normalization:**
- `attrpipe_norm_automap_ratio` — має зростати з часом
- `attrpipe_norm_disputed_total`, `attrpipe_norm_hitl_queue_depth{queue}`

**RAG:**
- `attrpipe_rag_route_total{route="exact_lookup|hybrid|refused"}` — зростання exact_lookup = зростання точності
- `attrpipe_rag_answer_duration_seconds{route}`
- `attrpipe_rag_citation_valid_ratio`

## 3. Конвенції логів

- Тільки structured JSON через `attrpipe.core.logging`; `print` заборонено (лінт T20).
- Обов'язкові поля кожного запису: `timestamp` (ISO, UTC), `level`, `service`, `event`.
- Наскрізна кореляція: `trace_id` + доменні ключі `raw_artifact_id`, `product_id`, `fact_id` — де застосовно. Одиниця роботи має простежуватись від fetch до answer.
- RAG-рішення логуються повністю: запит → маршрут → використані факти/чанки → відповідь (для еваля й розбору помилок, `06 §6`).
- **Заборонено в логах:** секрети, ключі, проксі-креденшели, персональні дані, повні тіла сторінок (тільки `raw_artifact_id`-посилання).
- Рівні: `DEBUG` — локальний дебаг; `INFO` — життєвий цикл одиниці роботи; `WARNING` — деградація з fallback-ом; `ERROR` — втрата одиниці роботи; `CRITICAL` — зупинка воркера.

## 4. Трейсинг

- OpenTelemetry span на кожен етап обробки одиниці; ім'я span = `<layer>.<operation>` (`fetch.static`, `extraction.tier4_llm`, `rag.exact_lookup`).
- Контекст пропагується через заголовки повідомлень черги (`traceparent`).
- Атрибути span — ті самі доменні ключі, що й у логах.

## 5. Алерти (мінімальний набір)

| Алерт | Умова (орієнтир) | Сенс |
|---|---|---|
| CoverageDrop | падіння `extraction_facts_total` по домену >50% за 24h | сайт змінив розмітку (drift) |
| BlockRateHigh | `fetch_blocked_total / requests_total` > 10% по домену | антибот ескалація → карантин |
| GroundingDrop | `grounding_pass_ratio` < 0.9 | LLM-екстракція галюцинує |
| HitlBacklog | `hitl_queue_depth` росте 3 дні поспіль | людська черга не встигає |
| QueueStalled | `queue_depth` > поріг і не падає | воркер лежить / backpressure |
| DiskRawStore | використання bucket > 80% | ретенція не працює |

Алерти — через Prometheus Alertmanager (прод); правила версіонуються в `infra/prometheus/`.

## 6. Дашборди (обов'язкові)

1. **Pipeline health:** глибини черг, throughput і error rate по шарах.
2. **Crawl ops:** блокування per домен, static/headless ratio, freshness.
3. **Quality:** auto-map rate, disputed ratio, grounding rate, route distribution, answer accuracy (з golden-прогонів).
4. **Cost:** LLM-токени, headless-хвилини, проксі-трафік.
