# Внешняя политика и изоляция, версия 0.6.0

Управляющий процесс хранит среду, seed, конфигурацию, truth и оценщик. Внешняя политика получает только публичные наблюдения через stdin и возвращает действия через stdout. Ни объект AuditEnv, ни reward/метрики оценки ей не передаются. Привилегированный oracle не допускается в этот worker.

## Два явных режима

| Режим | Назначение | Граница |
| --- | --- | --- |
| `docker` — по умолчанию | Контейнер внешней политики | Нет монтирования хостовых каталогов и docker.sock; сеть выключена, root filesystem только для чтения, UID 65534, capabilities сброшены, no-new-privileges, лимиты ресурсов |
| `development` | Локальная отладка доверенных политик | Только отдельный процесс и ограниченные pipes. Он может обращаться к файлам/сети хоста; не является режимом для недоверенного кода |

Если Docker или локальный образ недоступны, runner завершается ошибкой. Автоматического переключения в development нет. Прежние demo/benchmark остаются in-process development-командами; их режим не меняется молча.

## Протокол v1

Один JSON-объект на строку UTF-8; максимум 512 KiB на весь frame с переводом строки. Поля и ID запроса проверяются строго. Дубликаты ключей, NaN/Infinity, неправильный UTF-8, лишние поля, чрезмерная вложенность и несовпадающий номер запроса приводят к ограниченной ошибке протокола.

```json
{"protocol_version":1,"request_id":0,"observation":{"task":"...","manifest":{},"policy":{},"remaining_steps":100}}
```

Ответ:

```json
{"protocol_version":1,"request_id":0,"action":{"action":"list_records","params":{"table":"ledger","cursor":null,"limit":50}}}
```

Следующий observation содержит результат этого действия, request_id увеличивается на 1. Начальный manifest/policy передаётся один раз. После submit или truncation supervisor прекращает обмен и удаляет worker; terminal reward и диагностика не отправляются ему.

Протокол разрешает любой JSON в поле action: runtime-контракт среды отдельно проверяет действие и расходует шаг за неправильный запрос. Ошибка транспортного frame, EOF и тайм-аут обрывают эпизод с пустыми findings. В supervisor-отчёте отмечаются `worker_protocol_error`, `worker_exit` или `worker_timeout`; сырой stderr и некорректный frame не копируются в логи. Stderr направляется в null, чтобы флуд не заполнил память/диск оценщика.

Supervisor использует неблокирующее чтение и запись с общим deadline. Политика, которая не читает stdin, тоже не может бесконечно блокировать запись observation. Зависший subprocess завершается; для Docker дополнительно выполняется принудительное удаление контейнера по уникальному имени. Сбой инфраструктуры запуска отличается от ошибки политики.

## Запуск

В доверенном окружении с работающим Docker предварительно собрать образ:

```bash
docker build -f docker/worker.Dockerfile -t genesis-audit-worker:0.6.0 .
PYTHONPATH=src python -m genesis_fintech run-policy --seed 42 --config configs/interactions.json --output artifacts/container-example
```

Сборка требует сети для базового Python-образа. Сам runner использует только уже существующий локальный image ID через `--pull=never`; неизменяемый ID фиксируется в summary. Образ с объявленными VOLUME отвергается. Образ worker содержит только политики и общедоступные domain-примитивы, без evaluation/generation, записей, конфигов и артефактов. `.dockerignore` исключает остальное из build context.

Для локальной проверки протокола без Docker:

```bash
PYTHONPATH=src python -m genesis_fintech run-policy --seed 42 --config configs/interactions.json --backend development --output artifacts/subprocess-example
```

Выходная папка должна быть новой. В ней сохраняются public/private, trajectories.jsonl и summary.json на стороне оценщика. Они не монтируются worker. Код возврата CLI: 0 — политика завершила эпизод отправкой, 1 — truncation, 2 — ошибка запуска/параметров. Успешное завершение отправки не означает высокий F1.

## Ресурсы и доверенная база

Worker ограничен 1 CPU, 512 MiB RAM без дополнительного swap, 64 процессами, 128 file descriptors, tmpfs /tmp до 64 MiB, без core dump. По умолчанию 60 секунд wall-time, включая запуск контейнера, но без генерации/экспорта и предварительной проверки образа. Это ограничения worker; суммарное CPU/RAM supervisor+Docker ещё нужно замерить отдельно перед сдачей.

Доверяем ОС хоста, Docker daemon/runtime, supervisor и предварительно проверенному образу. Это не защита от уязвимостей ядра/контейнерного движка, не microVM и не сертификат безопасности. Нельзя предоставлять policy socket демона, privileged, host PID/network, bind mounts, дополнительные capabilities или секреты при сборке образа. Произвольные сторонние образы требуют отдельного review. Базовый образ закреплён digest, build-зависимость — версией и hash. Инструкции — RELEASE.md; cgroup/RSS-измерения и их область — RESOURCES.md.

## Проверка

Локальные тесты покрывают корректный обмен, побайтовое совпадение траекторий с прежними политиками, отсутствие host env/seed/truth в передаче, ошибочные/огромные frames, EOF, зависание, stderr-флуд, не читающий stdin worker, порядок request_id и отсутствие автоматического fallback.

Для настоящих Linux/Docker-проверок:

```bash
GENESIS_RUN_DOCKER_TESTS=1 PYTHONPATH=src python -m unittest discover -s tests -p test_container.py -v
```

При явном включении отсутствие Docker/образа — ошибка, а не пропуск. Проверяются отсутствие файлов хоста и evaluator-кода, запрет записи в root, внешней сети, UID/capabilities/no-new-privileges, ограничения памяти/CPU/PID, полный эпизод и удаление зависшего контейнера. Все 4 проверки прошли в [Linux CI 43570935768](https://github.com/larl9n/genesis-hackaton/actions/runs/43570935768) на коммите 42b10f6. Локальный Mac без Docker запускает только 142 обычных проверки; это различие сохраняется явно.

Настройки основаны на [официальной документации Docker run](https://docs.docker.com/engine/containers/run/) и [справочнике параметров](https://docs.docker.com/reference/cli/docker/container/run/).
