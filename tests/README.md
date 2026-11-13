# Проверки

Текущий набор — 87 тестов стандартного unittest без внешних runtime-зависимостей:

- `test_domain.py` — строгие схемы, неверные типы, время, суммы, Decimal и округление.
- `test_clean.py` — воспроизводимость, размеры на 50 seed, чистая модель и независимый checker.
- `test_storage_cli.py` — public/private, CSV/JSONL, round-trip, ограниченные ошибки и CLI.
- `test_scenario.py` — две причинные инъекции и независимая проверка эталона.
- `test_scoring.py` — строгие находки, matching, награда и попытки её обхода.
- `test_environment.py` — reset/step, инструменты, безопасный калькулятор, budgets и режимы.
- `test_scenario_cli.py` — файловый сценарий, score и полный oracle demo с траекторией.
- `fixtures/clean_minimal.json` — вручную составленный пример с двумя частичными платежами и остатком 4000 minor units. Он не создан генератором и нужен для независимой проверки.

```bash
make check PYTHON=.venv/bin/python
```

Матрица последующих этапов: [docs/VALIDATION.md](../docs/VALIDATION.md). Текущие тесты проверяют development-контракт и два семейства ошибок; они не подтверждают OS-изоляцию или отсутствующие FX/cutoff-сценарии.
