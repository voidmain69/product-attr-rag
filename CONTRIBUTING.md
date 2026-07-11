# Contributing

## Гілки та потік роботи

```
feature/<slug> ─┐
fix/<slug>     ─┼─ PR (squash) ─▶ develop ─ release PR (merge commit + tag) ─▶ main
chore/<slug>   ─┘
```

- **`main`** — тільки релізний стан. Захищена: прямі пуші заборонені, зміни виключно через релізний PR з `develop`.
- **`develop`** — дефолтна інтеграційна гілка. Уся робота вливається сюди через PR.
- Робочі гілки створюються **від `develop`**: `feature/<slug>`, `fix/<slug>`, `chore/<slug>`. Slug — короткий, kebab-case, англійською: `feature/shopify-adapter`.

## Коміти

Формат — [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`.

- `type`: `feat` | `fix` | `refactor` | `perf` | `test` | `docs` | `chore` | `ci`
- `scope` — шар пайплайну: `discovery`, `fetch`, `extraction`, `normalization`, `storage`, `rag`, `core`, `infra`, `tools`
- summary — наказовий спосіб, малою літерою, без крапки, ≤ 72 символи, англійською.

```
feat(extraction): add Shopify .json adapter (Tier 2)
fix(normalization): handle comma decimal separator in quantities
docs(rag): clarify disputed-fact answer format
```

Правила:
- Один коміт = одна логічна зміна. Не змішувати рефакторинг з фічею.
- Перед комітом: `python tools/dev.py check` — усе зелене. pre-commit хуки встановлені (`dev.py bootstrap`) і не обходяться (`--no-verify` заборонено).
- Секрети й `.env` не комітяться ніколи (gitleaks у pre-commit це ловить, але не покладайтесь лише на нього).

## Pull Requests

1. PR завжди у **`develop`** (крім релізних PR `develop → main`).
2. Малий і сфокусований: один PR = одна зміна одного шару. Зміна міжшарового контракту (`attrpipe.domain`, схема БД) — окремий PR разом з оновленням відповідного `docs/NN-*.md`.
3. Заповнити шаблон PR: що, навіщо, як тестувалось.
4. Обов'язково зелені: CI (ruff, format, mypy, pytest) + автоматичне Claude-ревью. Для змін у extraction/normalization/rag — прогін golden set (див. `docs/09-testing-requirements.md`).
5. Мерж у `develop` — **squash merge** (чиста лінійна історія). Релізний PR у `main` — **merge commit** + тег `vX.Y.Z`.
6. Гілка після мержу видаляється автоматично.

## Релізи

1. PR `develop → main` з заголовком `release: vX.Y.Z` і переліком змін.
2. Після мержу — тег: `git tag vX.Y.Z && git push --tags`.
3. Golden-прогін перед релізом обов'язковий; регресія метрик — блокер.

## Ревью: що дивимось і в якому порядку

1. **Незмінні принципи** (CLAUDE.md §2): провенанс, каскад за вартістю, ідемпотентність, версіонування, politeness. Порушення — блокер.
2. Коректність, крайові кейси, обробка помилок.
3. Тести: є, змістовні, відповідають `docs/09-testing-requirements.md`.
4. Читабельність і відповідність домену (терміни як у docs).

Стиль, який ловить лінтер, у ревью не обговорюється — це робота CI.
