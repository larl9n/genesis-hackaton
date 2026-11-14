# Проверки

Текущий набор — 142 обычных проверки и 4 Docker-интеграции стандартного unittest без внешних runtime-зависимостей:

- `test_domain.py` — строгие схемы, неверные типы, время, суммы, Decimal и округление.
- `test_clean.py` — воспроизводимость, размеры на 50 seed, чистая модель и независимый checker.
- `test_storage_cli.py` — public/private, CSV/JSONL, round-trip, ограниченные ошибки и CLI.
- `test_scenario.py` — две причинные инъекции и независимая проверка эталона.
- `test_scoring.py` — строгие находки, matching, награда и попытки её обхода.
- `test_environment.py` — reset/step, инструменты, безопасный калькулятор, budgets и режимы.
- `test_scenario_cli.py` — файловый сценарий, score и полный oracle demo с траекторией.
- `test_regressions.py` — исправленные malformed submit и переполнение календаря.
- `test_fx_clean.py` — чистые FX-платежи, локальная дата курса, границы периода, разрядности и совместимость конфигов.
- `test_full_scenarios.py` — четыре семейства, 16 комбинаций, два взаимодействия, ручные FX/cutoff-примеры, provenance, смена ID и до 12 ошибок.
- `test_refunds.py` — корректные возвраты, обратные проводки, достаточность прошлых поступлений и явная версия схемы.
- `test_baselines.py`, `test_benchmark.py` — независимые политики, сравнение и воспроизводимость отчётов/траекторий.
- `test_external.py` — отдельный процесс, строгий IPC, лимиты, EOF/timeout/cleanup и отсутствие fallback.
- `test_container.py` — 4 настоящие Docker-интеграции; отдельная Linux job включает их через GENESIS_RUN_DOCKER_TESTS=1. По умолчанию они пропущены.
- `fixtures/clean_minimal.json` — вручную составленный пример с двумя частичными платежами и остатком 4000 minor units. Он не создан генератором и нужен для независимой проверки.

```bash
make check PYTHON=.venv/bin/python
```

Матрица: [VALIDATION.md](../docs/VALIDATION.md). Docker-набор прошёл в [CI](https://github.com/larl9n/genesis-hackaton/actions/runs/43570935768); условия и границы — [ISOLATION.md](../docs/ISOLATION.md). Development subprocess и in-process benchmark не являются защищёнными режимами.
