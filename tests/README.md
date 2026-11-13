# Проверки

Текущий набор — 42 теста стандартного unittest без внешних runtime-зависимостей:

- `test_domain.py` — строгие схемы, неверные типы, время, суммы, Decimal и округление.
- `test_clean.py` — воспроизводимость, размеры на 50 seed, чистая модель и независимый checker.
- `test_storage_cli.py` — public/private, CSV/JSONL, round-trip, ограниченные ошибки и CLI.
- `fixtures/clean_minimal.json` — вручную составленный пример с двумя частичными платежами и остатком 4000 minor units. Он не создан генератором и нужен для независимой проверки.

```bash
make check PYTHON=.venv/bin/python
```

Матрица последующих этапов: [docs/VALIDATION.md](../docs/VALIDATION.md). Текущие тесты не проверяют отсутствующие инструменты агента, matcher награды или процессную изоляцию.
