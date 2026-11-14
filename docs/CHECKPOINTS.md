# Проверки по техническим этапам

## Блок B — единый оценочный запуск

Добавлены reset из сохранённых public/truth, evaluate-dataset и conformance-v1. На 20 эпизодах выполнены 80 development subprocess/oracle прогонов и 80 точных повторов, 20 grader-пар ID/order; все отправки независимо пересчитаны с диска. Reconciliation/oracle TP72/FP0/FN0; random TP0/FP80/FN72, flag-all TP8/FP592/FN64. Oracle остаётся привилегированным кодом оценщика, не внешним агентом.

5 новых тестов прошли: полные повторы/общие hashes, запрет регенерации, Docker fail-closed/no-overwrite, обнаружение подменённой метрики и CLI. Повторный полный набор: 166 тестов, 161 passed, 5 local skips. Настоящий Docker corpus-run проверяет Linux CI перед признанием блока B завершённым. Методика — [CONFORMANCE.md](CONFORMANCE.md).

## Блок A — train/dev-корпус

Подготовлены 10 train + 10 dev, 4 чистые компании, 72 метки, четыре семейства и обе композиции. 262–299 проводок, 135–150 документов. Public-only архив и index находятся в datasets/, служебные данные оценщика — в artifacts/public-corpus-v1. Seed и параметры dev не совпадают с train.

7 новых функциональных тестов проходят: воспроизведение каждого байта, публичность архива, раздельность наборов, строгий рецепт, независимая проверка без генератора, подмена truth с пересчитанным hash, symlink/path и повреждение архива, CLI/no-overwrite. Найден и исправлен сбой replay provenance после JSON round-trip: tuple/list сравниваются через каноническую сериализацию.

Полная повторная проверка пройдена: `make check` — 161 тест, 156 успешны, 5 локально skipped (4 Docker, 1 HTTP). Корпус дополнительно создан CLI и повторно проверен с replay=true. Ошибок, мешающих переходу к блоку B, не осталось. Команды и контракт — [DATASETS.md](DATASETS.md).

## UI по Hyperstudio-дизайну

Добавлен `serve` и локальная web-панель с настоящими прогонами доверенных политик. 8 новых тестов: 7 view/routing проходят локально, настоящий HTTP временно пропущен из-за запрета bind в текущей песочнице; в CI он обязателен. Полный локальный набор — 154 теста, 149 проходят, 5 skipped (HTTP + 4 Docker). JS синтаксически проверен Node VM.

В Chrome просмотрен первый экран index.html и AX с наполненными метриками, 4 находками, proof-документами и правильной маркировкой записанного примера. Mobile/dialog browser QA не завершён из-за нестабильного управления окнами; не считать это подтверждением responsive-вида. При обычном запуске serve доступны новые параметры; при file-preview доступны только записанные реальные seed42. Подробнее — [UI.md](UI.md).

Коммит e2182af опубликован; [CI 43573464612](https://github.com/larl9n/genesis-hackaton/actions/runs/43573464612) success, включая реальный HTTP-тест, Node-проверку JavaScript и 4 отдельные Docker-интеграции.

## Внешний worker, версия 0.4.0

`make check PYTHON=.venv/bin/python`: 146 тестов, 142 проходят, 4 Docker-интеграции пропущены локально (Docker отсутствует). Проверены правильные и ошибочные JSON-line frames, размеры, UTF-8/NaN/duplicate keys, request_id, EOF, hangs, блокирование записи, stderr-флуд, очистка процессов и отказ без Docker. In-process и subprocess траектории трёх политик совпадают.

Полный CLI-прогон `run-policy --seed 42 --config configs/interactions.json --backend development`: TP4/FP0/FN0, 12 действий, reward0.978. Артефакты: `artifacts/checkpoint-external-worker-2026-11-14`. Это проверка IPC, не OS-изоляции.

Все 4 реальные Docker-проверки прошли в [Linux CI 43570935768](https://github.com/larl9n/genesis-hackaton/actions/runs/43570935768) на коммите 42b10f6: закрытые файлы/код, сеть, read-only root, UID/caps/no-new-privileges, CPU/RAM/PID, полный эпизод и удаление зависшего контейнера. Job 132374954780: `Ran 4 tests ... OK`; обычная job также success. Протокол и доверенная база описаны в [ISOLATION.md](ISOLATION.md).

Обновлено: 14 ноября 2026 года. Локальное окружение: Python 3.11.18. Каждый этап проверялся до перехода к следующему.

| Этап | Реализовано | Проверка | Результат |
| --- | --- | --- | --- |
| 1. Публичные схемы и деньги | Manifest, policy, проводки, счета, платежи, распределения, FX; Decimal | 16 тестов в `test_domain.py`: типы, связи внутри записи, даты, округление, контекст Decimal, переполнение | Пройдено |
| 2. Чистая история и независимый checker | История до документов, полные/частичные/разбитые платежи, восстановление проводок | 16 тестов в `test_clean.py`, включая 50 seed, ручной пример и одинаковые суммы на разных счетах | Пройдено |
| 3. Файловый обмен и CLI | Шесть открытых файлов, отдельные truth/provenance, generate-clean/validate-clean | 11 тестов в `test_storage_cli.py`: round-trip, порча данных, запрет перезаписи, JSON/CSV ошибки | Пройдено |
| 4. Причинные ошибки и независимая истина | Дубль проводок счёта; частичное/полное отсутствие правильного кредита распределения | 11 тестов `test_scenario.py`: 50 seed, before/after, отключение семейств, отсутствие лишних/пропущенных меток и проверка доказательств | Пройдено |
| 5. Matching и общая награда | Строгие submissions/truth, one-to-one TP, штрафы FP, cost | 14 тестов `test_scoring.py`: oracle, abstention, clean false alarms, повторы, flag-all, неверные поля, максимальное matching, смена ID | Пройдено |
| 6. Development reset/step | Пять инструментов, калькулятор, шаги, timeout, train/evaluation, траектория | 17 тестов `test_environment.py`: опасные выражения, malformed/oversized input, пагинация, последняя отправка, тайм-аут, повторный submit, отсутствие приватных данных в наблюдениях | Пройдено |
| 7. Полный прогон из CLI | generate-scenario, validate-scenario, score, evaluator-only demo | 4 теста `test_scenario_cli.py`: файл→эталон→оценка, прежний и полный FX demo, согласованность траектории и score | Пройдено |
| 8. Исправления граничных сбоев | Calendar overflow и malformed submit без params | 2 теста test_regressions.py сначала воспроизвели оба сбоя, затем прошли после исправлений | Пройдено |
| 9. Чистые FX и границы периода | Явные базовые оценки, местная дата курса, документы до/после периода, legacy-конфиги | 8 тестов test_fx_clean.py, 50 seed и разные разрядности валют | Пройдено |
| 10. Полные и взаимодействующие сценарии | Четыре независимых семейства, fx_allocation и duplicate_cutoff | 13 тестов test_full_scenarios.py: 16 комбинаций, обе формы по 50 seed, неверная дата, ручные случаи, provenance, ID/order, 12 ошибок | Пройдено |
| 11. Корректные возвраты | Signed payments/allocations, обратные проводки, достаточность прошлых поступлений, схема v0.2 | 6 тестов test_refunds.py, включая 20 seed, ручной пример и ранний/чрезмерный возврат | Пройдено |
| 12. Обычные политики | Random, flag-all и reconciliation только через JSON-наблюдения | 9 тестов test_baselines.py: 50 profile/seed-пар, ручная композиция четырёх ошибок, opaque IDs/курсоры, разные валюты, максимум 12 находок, бюджет и tool errors | Пройдено |
| 13. Benchmark и failure analysis | Одинаковые эпизоды, привилегированный oracle отдельно, JSON/Markdown-отчёты и траектории | 3 теста test_benchmark.py: воспроизведение отчётов/траекторий, fingerprint файлов, отсутствие приватных полей, CLI, запрет перезаписи | Пройдено |

## Полная команда проверки

```bash
make check PYTHON=.venv/bin/python
```

Текущий набор: 130 тестов, CLI, компиляция и пять JSON-конфигов. Эта же команда входит в GitHub Actions. Предыдущие контрольные точки завершались наборами 42 и 87 тестов; расширение FX начиналось после 89 (с исправлениями), чистая FX-модель — после 97, четыре семейства и полный demo — после 111. После возвратов — 118; после политик и benchmark — 130.

## Сквозная проверка с диска

Выполнено в новой локальной папке:

```bash
.venv/bin/genesis-fintech generate-clean --seed 42 --config configs/clean.json --output artifacts/checkpoint-clean-2026-11-13
.venv/bin/genesis-fintech validate-clean artifacts/checkpoint-clean-2026-11-13/public
```

Результат обеих команд: `ok=true`, 50 счетов, 66 платежей, 232 проводки, ошибок согласованности нет. Это 116 документов, соответствует предлагаемому стандартному размеру. Артефакты исключены из Git; существующую папку команда не перезаписывает.

## Что именно подтверждено

- Одинаковые seed/config воспроизводят историю и документы; глобальное состояние random не меняется.
- Допустимые частичные и разбитые платежи принимаются, непогашенная дебиторская задолженность не объявляется ошибкой.
- Сбалансированные дубли проводок отвергаются, несмотря на равенство общего дебета и кредита.
- Неизвестные ссылки, повторные IDs, несовпадающие суммы, неверные валюты и край периода проверяются.
- Чтение public не обращается к соседним private-файлам; это проверено удалением truth и порчей provenance.
- Правила CSV null и строгих JSON-схем проверены после записи и чтения.

## Граница готовности

Подтверждены чистая модель с FX/возвратами/граничными документами, четыре семейства, две композиции и базовые политики в development API. OS-изоляция, наборы train/dev и окончательная упаковка ещё впереди. Права 0700/0600 на private не изолируют недоверенный процесс под тем же пользователем. Проверки не являются заключением о реальных книгах.

## Полный эпизод с ошибками

Выполнено:

```bash
.venv/bin/genesis-fintech demo --seed 42 --config configs/scenario.json --output artifacts/checkpoint-episode-2026-11-13
.venv/bin/genesis-fintech validate-scenario artifacts/checkpoint-episode-2026-11-13
```

Результат: две независимо подтверждённые ошибки, TP=2, FP=0, FN=0, F1=1, 11 действий (10 запросов доказательств + submit), terminal reward=0.98. Записаны public/private, trajectories.jsonl и summary.json. Тест повторно оценивает сохранённую отправку с тем же числом inspection steps и получает ту же награду.

Oracle имеет закрытый эталон на стороне оценщика. Это проверка достижимости F1=1 и работоспособности цепочки, не измерение способности агента или качества обучения. Политика и оценщик пока не изолированы процессами.

## Четыре семейства, композиции и возвраты

Проверенный прогон версии 0.2.0:

```bash
.venv/bin/genesis-fintech demo --seed 42 --config configs/interactions.json --output artifacts/checkpoint-four-families-refunds-2026-11-13
.venv/bin/genesis-fintech validate-scenario artifacts/checkpoint-four-families-refunds-2026-11-13
```

Результат: четыре подтверждённые ошибки, TP=4, FP=0, FN=0, F1=1, 12 действий (11 запросов + submit), reward=0.978. В clean-истории есть 12 счетов с иностранными поступлениями, четыре граничных случая и четыре возврата. Прочитаны реальные FX evidence через инструмент get_record(table=fx), ошибок инструментов нет. Тест максимальных 12 ошибок также завершается в бюджете 100 шагов.

## Сравнение политик, версия 0.3.0

```bash
PYTHONPATH=src .venv/bin/python -m genesis_fintech benchmark --output artifacts/checkpoint-baselines-2026-11-14
```

50 эпизодов × 4 политики = 200 прогонов, 140 меток, 10 чистых компаний. Reconciliation и oracle: TP=140, FP=0, FN=0. Random: TP=0, FP=200, FN=140. Flag-all: TP=22, FP=1478, FN=118. Пагинация позволяет reconciliation тратить в среднем 11.6 шага, oracle с отдельными запросами — 12.2; это объясняет небольшую разницу награды при одинаковом F1. Измеренные результаты, причины ошибок и ограничения — [BASELINES.md](BASELINES.md). Полный report и 200 JSONL-траекторий хранятся локально в artifacts и не публикуются.

## Блоки A/B: замороженный корпус и независимый прогон

10 train + 10 dev, четыре чистые компании, 72 метки. Public-only архив SHA-256 `408c1cef6dc2257879d4b441f046642d0de1553c570129207401e83c68984e50`. Проверены hashes, независимый эталон, версии, размеры и воспроизведение. Исправлено сравнение tuple/list provenance после JSON round-trip.

166 локальных тестов: 161 passed, 5 skips (4 Docker и 1 HTTP из-за ограничений хоста). [Linux CI 43588068060](https://github.com/larl9n/genesis-hackaton/actions/runs/43588068060) прошёл обычную проверку, четыре Docker-интеграции и полный corpus-run: 80 прогонов + 80 точных повторов + 20 ID/order grader-пар. Reconciliation и evaluator-only oracle: TP72/FP0/FN0; все четыре чистые компании без ложных тревог. Random TP0/FP80/FN72; flag-all TP8/FP592/FN64. Это публичный синтетический корпус, не hidden test и не официальный стенд.

## Блок C: ресурсы

Добавлено чтение memory.peak, memory.max, cpu.stat и memory.events cgroup v2 до завершения worker. Доверенный фиксированный reader включён в измеренный пик, работает под UID65534 и не получает новых mounts/capabilities. Оценщик требует измерения для каждого Docker-прогона, проверяет отсутствие OOM и предел 512 MiB / 60 секунд. RSS supervisor/CLI и cgroup peak worker записываются отдельно; Docker daemon и ядро не входят в измерение. Полный лимит физического хоста 2 CPU / 4 GB этим не сертифицируется. [CI 43588561164](https://github.com/larl9n/genesis-hackaton/actions/runs/43588561164) прошёл: все основные worker counters и повторы приняты, OOM=0; max worker peak 25 141 248 bytes, max worker elapsed <0.376s, весь suite 53s.

## Блок D: комплект 0.5.0

MIT, runtime/test lock (stdlib only), hash-pinned build lock, Docker base digest, source/wheel builder и offline verifier. Allowlisted архив воспроизводится побайтово; каждый файл проверяется по SOURCE-MANIFEST. Изменённый source и symlink отвергаются; локальная переписка и закрытые данные не включаются. Три новые упаковочные проверки прошли. Полная локальная проверка: 170 тестов, 165 passed, 5 local skips. Предварительный чистый install wheel + demo + полный source-suite прошёл; финальная сборка и Linux CI выполняются отдельно. Команды — RELEASE.md, сценарий показа — DEMO.md.
