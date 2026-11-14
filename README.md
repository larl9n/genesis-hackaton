# Genesis FinTech Environment

Воспроизводимая RL-среда для ИИ-аудитора. Агент исследует синтетические финансовые записи, собирает доказательства и отправляет найденные расхождения. Независимый оценщик сопоставляет выводы с закрытым эталоном.

Проект команды участников **Genesis Hackathon**: Алишер, Абильтаир, Сатти, Алимасуд.

## Статус

**Версия 0.4.0: внешний worker и контейнерный backend.** Работают история с FX/возвратами/границами, четыре семейства ошибок и две композиции, независимая проверка, matching/reward, инструменты и политики. Добавлен JSON-line IPC с ограничениями размера/времени и отдельный процесс политики. Docker-backend по умолчанию ограничивает файлы, сеть и ресурсы и не переключается в небезопасный режим при ошибке. Контейнерная проверка выполняется отдельной job Linux CI; локальный режим development сам по себе OS-изоляцию не подтверждает. Дополнительно встроен локальный UI по Hyperstudio-дизайну: сценарии, метрики, доказательства и траектория. Train/dev-наборы и полный пакет сдачи — следующие этапы.

Код опубликован в `main`; [CI версии 0.4.0](https://github.com/larl9n/genesis-hackaton/actions/runs/43570935768) прошёл: 142 обычные проверки и 4 реальные Linux/Docker-интеграции в отдельной job.

[Исходное ТЗ](https://docs.google.com/document/d/13a2pVl5LVU6_MW_FWE4KvjX_s7e-UPJvcSJuYjvCWoA) — черновик организаторов от 12 ноября 2026 года. Его лимиты и правила пока рассматриваем как проектные ориентиры. Дедлайн команды — до 20 ноября; сдаваемую версию готовим к 19 ноября.

## Обязательный результат

- Генератор согласованной истории компании и синтетических документов.
- Четыре независимо настраиваемых семейства ошибок: дубли счетов, распределение платежей, FX, отчётный период.
- Минимум два сценария взаимодействующих ошибок, чистые компании и корректные отвлекающие случаи.
- Контракт `reset/step` и пять ограниченных инструментов агента.
- Оценка структурированных выводов с доказательствами и общая функция награды.
- Четыре базовые политики, 10 train + 10 dev эпизодов, траектории, проверки и воспроизводимая демонстрация.

Для обязательной реализации не нужны платные API и GPU. Отдельный сайт и обучение весов модели необязательны. Все финансовые данные синтетические.

## Замороженные train/dev и единая оценка

В `datasets/public-v1.tar.gz` находятся 10 train + 10 dev эпизодов без скрытых ответов; index содержит hashes. Полный корпус для оценщика воспроизводится из рецепта:

```bash
PYTHONPATH=src python -m genesis_fintech generate-dataset --spec configs/dataset.json --output artifacts/public-corpus-v1
PYTHONPATH=src python -m genesis_fintech validate-dataset artifacts/public-corpus-v1 --replay
PYTHONPATH=src python -m genesis_fintech evaluate-dataset artifacts/public-corpus-v1 --output artifacts/corpus-evaluation --replay
```

Оценка по умолчанию требует заранее собранный Docker worker image. Три обычные политики работают с одинаковыми сохранёнными записями; oracle остаётся на стороне оценщика. Выполняются 80 прогонов, 80 повторов и 20 grader-пар ID/order; формируются метрики, отчёт и траектории. Явный `--backend development` разрешён только для доверенной локальной проверки. [Данные](docs/DATASETS.md), [методика](docs/CONFORMANCE.md).

## Быстрый старт

### Открыть UI

```bash
.venv/bin/python -m genesis_fintech serve
```

Откройте **http://127.0.0.1:8765**: выбор сценария, seed и политики, метрики, находки, доказательства, траектория и экспорт JSON. Без сервера можно открыть `src/genesis_fintech/web/static/index.html` — он показывает явно помеченные записи настоящих прогонов seed42. Новые параметры требуют сервера. Node/npm не нужны. [Описание UI](docs/UI.md).

### Подготовить Python

Целевая версия — **Python 3.11**. Runtime-зависимостей на этапе каркаса нет. Для новой копии репозитория установите Python 3.11 и создайте окружение:

```bash
git clone https://github.com/larl9n/genesis-hackaton.git
cd genesis-hackaton
python3.11 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python -m genesis_fintech doctor
PYTHONPATH=src python -m genesis_fintech info
```

Если репозиторий уже открыт локально, начните с создания `.venv` в его папке. Установка пакета через pip для этих команд не требуется.

В текущей рабочей копии `/Users/zhopa/genesis-fintech-env` окружение уже подготовлено на Python **3.11.18**. Здесь достаточно выполнить:

```bash
source .venv/bin/activate
make check PYTHON=python
```

Локальная сборка Python хранится в `.tools/python`; `.venv` ссылается на неё. Эти каталоги не входят в Git, поэтому новый клон требует своего окружения.

`doctor` проверяет версию Python и завершает работу с ненулевым кодом при версии ниже 3.11. `info` выводит JSON с текущими возможностями и запланированными компонентами.

## Создать и проверить чистую компанию

После активации `.venv`:

```bash
PYTHONPATH=src python -m genesis_fintech generate-clean --seed 42 --config configs/clean.json --output artifacts/clean-example
PYTHONPATH=src python -m genesis_fintech validate-clean artifacts/clean-example/public
```

Первая команда сначала строит историю операций, затем выводит документы и проводки, проверяет их, сохраняет файлы и повторно проверяет чтение с диска. Вторая независимо восстанавливает ожидаемые проводки из открытых документов. При успехе результат содержит `"ok": true`. Код возврата 1 означает несогласованные книги, 2 — ошибку формата, параметров или файлов.

По умолчанию создаётся 50 счетов с полными, частичными и разбитыми платежами. Каждая компания использует одну базовую валюту. Каталог результата должен быть новым: существующий не перезаписывается. Для маленького примера можно добавить `--invoices 3`.

```text
artifacts/clean-example/
  public/   # manifest.json, policy.json, ledger.csv, invoices.jsonl, payments.jsonl, fx.csv
  private/  # truth.json с пустым issues; provenance.json с seed, конфигурацией и историей
```

Clean-команды предназначены только для чистых данных. История v0.2 допускает платежи в другой валюте с явной конвертацией в базовую валюту книги, обоснованные возвраты и документы до/после периода; сами проводки всегда выражены в базовой валюте. Счета в иностранной валюте и переоценка валютного остатка не моделируются. Раздельные папки не обеспечивают изоляцию процесса агента.

## Полный эпизод и оценка

```bash
PYTHONPATH=src python -m genesis_fintech demo --seed 42 --config configs/interactions.json --output artifacts/demo-example
PYTHONPATH=src python -m genesis_fintech validate-scenario artifacts/demo-example
```

Демонстрация создаёт компанию, запускает evaluator-only oracle через ограниченные действия среды и сохраняет `public/`, `private/`, `trajectories.jsonl`, `summary.json`. Oracle знает эталон и проверяет достижимость правильной оценки; его результат не измеряет способность агента. Для seed 42 и interactions.json: TP=4, FP=0, FN=0, F1=1, 12 шагов, reward=0.978.

Конфиги: `clean.json` — прежний чистый пример, `scenario.json` — прежние два семейства (v0.1), `full.json` — четыре независимых семейства, `interactions.json` — четыре семейства с двумя взаимодействиями (v0.2). Старые конфиги принимаются без добавления новых ошибок; воспроизведение фиксирует также версию генератора.

Для генерации без oracle используйте `generate-scenario` с теми же аргументами. Собственные находки оцениваются на стороне управляющего процесса:

```bash
PYTHONPATH=src python -m genesis_fintech score artifacts/demo-example --findings findings.json --inspection-steps 11
```

`findings.json` должен содержать `{episode_id, findings}` по [контракту](docs/ENVIRONMENT.md). `score` и `validate-scenario` читают private truth и не входят в набор инструментов политики.

Python API: `from genesis_fintech.environment.core import AuditEnv`, затем `env.reset(seed, config)` и `env.step(action)`. В режиме `evaluation` шаги скрывают награду и диагностику; управляющий процесс получает итог через `evaluation_result()` после завершения. **Текущая реализация находится в одном процессе и не является защищённым held-out запуском.**

Опционально установить пакет вместе с CLI:

```bash
python -m pip install -e .
genesis-fintech doctor
```

Установка через pip может потребовать сеть для получения build-зависимостей. Финальная оценка должна выполняться без сети после подготовки окружения.

При наличии `make` доступны `make doctor`, `make info` и `make check`. После активации окружения укажите `PYTHON=python`; значение по умолчанию — `python3.11`.

## Сравнить базовые политики

```bash
PYTHONPATH=src python -m genesis_fintech benchmark --output artifacts/baseline-example
```

Пять профилей × десять seed = 50 одинаковых эпизодов для каждой из четырёх стратегий. Сохраняются JSON/Markdown-отчёты, public/private и отдельные траектории. Для короткого прогона добавьте `--seeds 42`. Папка результата должна быть новой.

В проверенном прогоне reconciliation: TP=140, FP=0, FN=0; random F1=0, flag-all micro F1=0.0268. Это измерение на нашем синтетическом development-наборе в одном процессе. Oracle имеет привилегированный эталон; обучения модели и OS-изоляции здесь нет. Методика, ограничения и разбор ошибок — [BASELINES.md](docs/BASELINES.md).

## Внешняя политика

```bash
docker build -f docker/worker.Dockerfile -t genesis-audit-worker:0.4.0 .
PYTHONPATH=src python -m genesis_fintech run-policy --seed 42 --config configs/interactions.json --output artifacts/container-example
```

По умолчанию требуется Docker и заранее собранный образ. Без Docker для доверенного локального кода можно явно добавить `--backend development`; это отдельный процесс с тем же протоколом, но без ограничений доступа к хосту. Протокол, ресурсы и проверки — [ISOLATION.md](docs/ISOLATION.md).

## Структура

```text
src/genesis_fintech/
  cli.py          # генерация, валидация, score, demo, benchmark и run-policy
  contracts.py    # типы и Protocol обмена среды и политики
  domain/         # строгие модели записей и Decimal-конвертация
  generation/     # история, четыре инъекции и две композиции, сохранение/чтение
  environment/    # reset/step, ограниченные инструменты и калькулятор
  evaluation/     # проверки, reward, benchmark и supervisor внешнего worker
  policies/       # базовые политики, JSON-line протокол и worker
docker/           # минимальный образ политики без эталона и оценщика
configs/          # чистые, независимые и взаимодействующие сценарии
docs/             # архитектура, контракт, данные, проверки и этапы
tests/            # предметные проверки, IPC, отдельные Docker-интеграции
.github/          # CI и шаблоны для GitHub
```

## Документация

| Документ | Содержание |
| --- | --- |
| [Архитектура](docs/ARCHITECTURE.md) | Модули, поток данных и границы доступа |
| [Интерфейс](docs/UI.md) | Дизайн, локальный запуск, живые прогоны и записанные примеры |
| [Изоляция и внешний worker](docs/ISOLATION.md) | Запуск run-policy, протокол, ограничения, Docker и проверка |
| [Контракт среды](docs/ENVIRONMENT.md) | Действия, наблюдения, завершение, награда |
| [Данные](docs/DATA.md) | Открытые записи, закрытый эталон, деньги и доказательства |
| [Ошибки и эталон](docs/ISSUES.md) | Причинные изменения, affected IDs, суммы расхождений и evidence sets |
| [Разработка](CONTRIBUTING.md) | Окружение, работа с изменениями и проверки |
| [Проверки](docs/VALIDATION.md) | Критерии корректности и будущая матрица тестов |
| [Политики и результаты](docs/BASELINES.md) | Сравнение четырёх стратегий, воспроизведение и разбор ошибок |
| [Результаты этапов](docs/CHECKPOINTS.md) | Выполненные этапы, команды проверки и границы готовности |
| [Этапы](docs/ROADMAP.md) | Последовательность реализации без назначения задач людям |
| [Решения и вопросы](docs/DECISIONS.md) | Принятые решения и незакрытые вопросы |
| [Контекст для продолжения](docs/PROJECT_CONTEXT.md) | Решения пользователя, готовые файлы, проверки и команда возврата к чату |

## Проверка каркаса

```bash
PYTHONPATH=src python -m genesis_fintech doctor
PYTHONPATH=src python -m genesis_fintech info
python -m compileall -q src
python -m json.tool configs/default.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

`make check PYTHON=python` проверяет CLI, предметную логику, IPC, компиляцию и пять JSON-конфигов: 149 тестов проходят локально; 4 Docker-интеграции и 1 настоящий HTTP-тест пропущены из-за ограничений текущей среды. В Linux CI отдельная job явно включает Docker-тесты; обычная job обязана выполнить настоящий HTTP-тест. Контейнерный набор ранее прошёл в CI версии 0.4.0. Проверены четыре семейства, 16 комбинаций, две композиции, ручные FX/cutoff и полный внешний эпизод. Это проверка выбранного контейнерного режима, не гарантия защиты от уязвимостей ядра или Docker.

## Лицензия

Лицензия ещё не выбрана. Перед сдачей нужно выбрать её и добавить файл `LICENSE` согласно требованиям кейса.
