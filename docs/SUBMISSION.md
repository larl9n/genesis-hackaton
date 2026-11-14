# Приёмка комплекта по кейсу Genesis

Проверка от 14 ноября 2026 года. [Исходный документ](https://docs.google.com/document/d/13a2pVl5LVU6_MW_FWE4KvjX_s7e-UPJvcSJuYjvCWoA) повторно прочитан через Google Docs; metadata modifiedTime — 2026-11-12T16:26:51.813Z. Английская и русская вкладки по-прежнему называют его черновиком для организаторов. Нет основания считать предложенные лимиты и баллы утверждёнными.

## Соответствие обязательному объёму

| Требование | Реализация и проверяемое свидетельство |
| --- | --- |
| Сначала согласованная история, затем причинные изменения | generation/clean.py, scenario.py; independent checker, provenance; test_clean, test_full_scenarios, test_refunds |
| Четыре независимых семейства, два взаимодействия | configs/full.json, interactions.json; 16 сочетаний и независимая проверка truth/evidence |
| Чистые данные, split/refund/repeated-amount decoys | Генератор и публичные train/dev; DATASETS.md, test_fx_clean, test_refunds |
| Деньги, FX, timestamps, схемы и policy | domain/models.py, money.py, fx.py; DATA.md и ENVIRONMENT.md; bool/float/unknown fields отклоняются |
| reset/step и пять ограниченных инструментов | environment/core.py; test_environment, test_regressions; до 50 строк и 100 действий |
| Отдельный агент без truth/seed/сети и доступа к оценщику | Docker worker и narrow JSON bridge; четыре реальные Linux Docker-интеграции; ISOLATION.md |
| Общая награда, один к одному, отсутствие duplicate credit | evaluation/scoring.py, findings.py; test_scoring; сравнение с abstention/false alarms |
| Четыре базовые стратегии | random, flag-all, reconciliation + привилегированный evaluator-only oracle; BASELINES.md |
| 10 открытых train + 10 dev | datasets/public-v1.tar.gz/index; configs/dataset.json; hashes и точное восстановление |
| JSONL с полным переходом и безопасным train reward | examples/training-v1/trajectories.jsonl + initial_observations + manifest; collect/validate-trajectories; TRAINING.md |
| Полный повтор и перестановка/переименование | conformance-v1: 80 runs + 80 replays + 20 grader-пар; CONFORMANCE.md |
| Лицензия, зависимости, контейнер и одна команда | MIT, requirements*.lock, pinned Docker base; make evaluate; RELEASE.md |
| Сквозная демонстрация и краткая записка | DEMO.md; устройство и ограничения ниже; установленный wheel воспроизводит demo и train example |
| Измеренный разбор ошибок, шагов и времени | BASELINES.md, report.json/report.md; RESOURCES.md разграничивает process RSS, cgroup peak и память ОС |

Текущий public corpus содержит четыре чистые компании и четыре компании с обеими композициями. Это публичная демонстрация. Указанные в разделе 6 ТЗ 20 скрытых эпизодов с пятью чистыми и пятью взаимодействиями относятся к стенду организаторов; мы не выдаём публичный corpus за этот стенд и не меняем его задним числом.

## Краткая записка об устройстве

Supervisor создаёт согласованную латентную историю, выводит документы и проводки и записывает изменения каждого инъектора. Независимый checker восстанавливает ожидаемые записи из публичных документов. Truth принимается лишь после проверки полноты, суммы и доступных доказательств. Integer minor units и Decimal-конвертация предотвращают неявное смешение валют.

Обычная политика получает только наблюдения через ограниченные инструменты. В оценке worker работает в контейнере без сети и mounts; supervisor проверяет действия, считает общую награду и сохраняет переходы. Oracle остаётся только у оценщика. Обучающий exporter использует доверенные встроенные политики в процессе supervisor; это отдельная операция, не контейнерная оценка и не обучение модели.

Matching один к одному требует типа, affected IDs, суммы, валюты и полного evidence set. Ложные выводы и повторы ухудшают F1, стоимость запросов лишь слегка различает одинаково правильные ответы. Train возвращает терминальную награду, evaluation скрывает её. Все публичные примеры можно перепроверить по сохранённым действиям.

## Границы подтверждения

Собственные тесты не дают официальных баллов. Нет результатов официального hidden harness, политик организаторов или проверки на их слабейшем разрешённом хосте. Наши 20 ID/order-проверок проверяют grader и обоснованный oracle submission; это не полные прогоны всех политик на 20 преобразованных компаниях.

Контейнерная защита доверяет ядру и Docker. Замеры cgroup/RSS не включают весь Docker daemon и ОС, поэтому полный физический бюджет 2 CPU / 4 GB пока не сертифицирован. Модель финансового мира ограничена, rule-based reconciliation не является реальным аудитором. Обучение весов и улучшение LLM не заявляются. UI необязателен; mobile/dialog visual QA ещё не подтверждён.

## Перед отправкой

Комплект: source archive, wheel, SHA256SUMS, отчёты/траектории, ссылка на проверенный commit и CI. В source archive уже есть train JSONL; полные Docker-отчёты доступны отдельным Actions artifact. Сначала выполните инструкции RELEASE.md и репетицию DEMO.md.

Организаторы должны подтвердить финальный регламент, формат и точное время приёма, доступность hidden harness и правила исправлений. В исходном документе это остаётся release gate организаторов. Автоматическая отправка проекта, регистрация или сообщения организаторам этим блоком не выполняются.
