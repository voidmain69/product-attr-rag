# Extraction benchmark

Універсальний, data-driven бенчмарк здобуття характеристик. Міряє **accuracy**
(частка очікуваних атрибутів, здобутих з правильним канонічним значенням) і
**coverage** (частка, для якої здобуто хоч якесь значення) у розрізі
вендор / категорія / загалом, плюс розподіл по тірах екстракції.

Детермінований: без мережі, без LLM (docs/09 §2) — ганяє реальні Tier 1 (JSON-LD),
Tier 2 (CMS), Tier 3 (DOM) екстрактори + нормалізатор на збережених фікстурах.

## Запуск

```bash
python tools/dev.py benchmark          # звіт + список промахів
python tools/benchmark.py              # тільки звіт
python tools/benchmark.py --failures   # + перелік missing/wrong по атрибутах
python tools/benchmark.py --json        # машинний JSON (для дашбордів/CI)
```

## Як додати вендора або категорію (без коду)

Створи теку `cases/<vendor>/<category>/<slug>/` з двома файлами:

```
cases/asus/motherboards/rog-strix-b650e-f/
    source.html      # збережений сирий артефакт (або source.json)
    expected.json    # identity + очікувані канонічні значення
```

`expected.json`:

```json
{
  "product": {"brand": "ASUS", "name": "...", "source_url": "https://..."},
  "content_type": "text/html",
  "expected": {"socket": "AM5", "form_factor": "ATX", "memory_slots": 4}
}
```

- `expected` ключі — це `attribute_key` з онтології (`attrpipe.normalization.ontology`).
  Числові значення звіряються з допуском; текстові — точним збігом канонічного значення.
- `content_type` опційний — інферситься з імені файлу (`source.html` → `text/html`,
  `source.json` → `application/json`).
- Якщо атрибута ще немає в онтології — додай його туди (синоніми роблять мапінг),
  версію онтології бампни, не переписуючи наявні атрибути (CLAUDE.md §2.4).

Правила фікстур ті самі, що й у `tests/fixtures/`: без персональних даних і секретів,
жодного живого краулінгу.

## Що всередині зараз

| Вендор | Категорії |
|--------|-----------|
| ASUS   | motherboards, monitors, laptops |
| MSI    | graphics_cards, motherboards |
| Intel  | processors |
