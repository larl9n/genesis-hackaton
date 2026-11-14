# Состояние проекта для продолжения

Обновлено: 14 ноября 2026 года. Engine — **0.5.0**, кандидат для сдачи. Последняя локальная проверка: 170 тестов, 165 passed, 5 local skipped. Блоки A/B/C опубликованы и прошли Docker corpus-run в CI. Блок D проходит финальную проверку комплекта. Сайт отложен. Последующие указания пользователя имеют приоритет над этим файлом.

## Проект и требования

- Папка: `/Users/zhopa/genesis-fintech-env`.
- GitHub: `https://github.com/larl9n/genesis-hackaton`, ветка main.
- [Исходное ТЗ](https://docs.google.com/document/d/13a2pVl5LVU6_MW_FWE4KvjX_s7e-UPJvcSJuYjvCWoA/edit?tab=t.ahihtw8b8mj) уже прочитано через Google Drive. Это черновик организаторов от 12 ноября; предложенные лимиты не следует выдавать за утверждённый регламент.
- Команда участников хакатона: Алишер, Абильтаир, Сатти, Алимасуд. Дедлайн — до 20 ноября 2026 года; ориентир готовой сдачи — 19 ноября, точный час приёма неизвестен.
- Нужна воспроизводимая RL-среда финансового аудита: синтетическая согласованная история, четыре семейства ошибок, инструменты, эталон, награда, траектории и проверка. Платёжный сайт, реальные финансовые данные, GPU и обучение весов модели не требуются.
- По черновику: 200–2000 проводок, 20–200 документов, 0–12 ошибок; 100 шагов с submit, страницы до 50 строк, 60 секунд, Python 3.11, 2 CPU, 4 GB RAM. Дополнительно нужны две композиции ошибок, чистые компании, split/refund/repeated-amount decoys, четыре политики, 10 train + 10 dev, лицензия, lockfile, контейнерные инструкции и демонстрация.

## Указания пользователя

1. Сначала просил архитектуру, README и небольшой каркас; затем явно разрешил техническую реализацию по этапам.
2. После каждого этапа запускать необходимые функциональные проверки. Найденные ошибки исправлять, затем продолжать. Не останавливаться на предложении плана.
3. Распределение задач между участниками отменено словами «на задачи забей, не надо». Не возвращать его без запроса.
4. Ранее дизайн сайта был отложен; затем пользователь явно заказал UI/UX по файлу `hyperstudio.org-DESIGN.md`. Теперь интерфейс реализуется внутри существующего проекта, без отдельного хостинга. Основной кейс и распределение задач не меняются.
5. Пользователь просил сохранить историю, чтобы не повторять объяснения. Локальный снимок `docs/CHAT_HISTORY.md` исключён из Git. Этот контекст и AGENTS.md предназначены для продолжения.
6. После аудита 0.3.0 пользователь разрешил продолжить разработку при успешной повторной проверке. Проверка 130 тестов прошла; начат этап внешнего worker/IPC и Docker-изоляции. Сайт и распределение задач по-прежнему не нужны.
7. Последний реализованный этап — UI по `hyperstudio.org-DESIGN.md`. Файл прочитан полностью. Стиль: black/sand, 850px rails, silver keys, ordered dot sculpture, компактная типографика. Существующее ядро используется для функциональных результатов, не переписывается на JS.
8. После UI пользователь попросил перечислить оставшиеся основные функции и сказал, что сайт будем развивать позже. Текущий приоритет — основной кейс: train/dev, единый изолированный оценочный прогон, измерения и упаковка. Не продолжать косметическое развитие UI без нового запроса.
9. Пользователь поручил после каждого блока делать вывод, повторно проверять, исправлять ошибки и автоматически продолжать при успехе. Выбор лицензии подтверждён ответом «1» на варианты — MIT. Не спрашивать повторно разрешение на эти этапы.

## Что работает

- Блок A: `generation/datasets.py`, configs/dataset.json, 10 train + 10 dev, раздельные seed и новые параметры dev; 4 чистые компании, 72 метки. Public-only архив datasets/public-v1.tar.gz и публичный index готовы к публикации; private корпус в artifacts/public-corpus-v1. Строгие hashes/размеры/покрытие, независимый truth-check, replay, no-overwrite, symlink/path rejection. 7 тестов проходят, полная повторная проверка: 161 найден, 156 passed, 5 local skips. Исправлено tuple/list сравнение provenance после JSON round-trip. См. DATASETS.md.
- Блок B завершён: evaluate-dataset читает сохранённые записи, запускает 3 внешние политики + evaluator-only oracle, пересчитывает отправки с диска, проверяет 20 ID/order grader-пар и опционально 80 точных повторов. Development 80+80 прогонов прошёл: reconciliation/oracle TP72/FP0/FN0. Настоящий Docker corpus-run и повторы прошли в Linux CI 43588068060 (commit 33b3bc34fac88730fb638024b54dc838766c59fd). См. CONFORMANCE.md.

- `web/`: локальная презентация и демо-панель без Node/npm/frameworks. CLI `serve --port 8765`, loopback-only stdlib HTTP. 3 сценария × 3 обычные политики, seed 0..2147483647, настоящие метрики/находки/observed evidence/траектория и JSON-export. Только доверенные in-process политики, не Docker и не обучение модели. Ни truth/provenance, ни произвольные пути/команды через UI не доступны.
- `web/static/`: стили по дизайн-ТЗ, SVG из 6063 детерминированных точек, dark laboratory и light evidence board, tabs/dialog/reduced-motion/адаптивные CSS. При открытии index.html как файла — явно помеченные записи seed42; seed/policy заблокированы, scenario меняет записанный пример. `scripts/build_ui_samples.py` воспроизводит реальные view-модели, тест сверяет их с движком. Для новых seed нужен serve. Все ассеты локальные; шрифты используют заявленные font stacks с системным fallback.
- UI API: явный allowlist static, строгие Host/Origin и application/json, 4 KiB запрос, максимум 2 активных вычисления, CSP/nosniff/frame denial. Публичный production hosting не настраивался.

- `domain/models.py`: строгие публичные runtime-модели, bool/float в денежных полях запрещены, неизвестные поля отклоняются. Новый public schema_version=0.2 допускает signed payments/allocations для возвратов; положительная v0.1 поддержана, возвраты под v0.1 отвергаются.
- `domain/money.py`: Decimal-конвертация minor units с явными экспонентами и округлением, независимо от глобальных Decimal precision/traps.
- `domain/fx.py`: принадлежность полуоткрытому периоду, локальная дата платежа в manifest.timezone, точный выбор публичной котировки, базовая оценка.
- `generation/clean.py`: сначала согласованная латентная история, затем документы и проводки. Счета и книга в базовой валюте; поступления могут быть иностранными. Поддержаны частичные/разбитые платежи, возвраты и документы у обеих границ периода. Генератор engine v0.2.0, только локальный RNG.
- `evaluation/clean.py`: независимо восстанавливает проводки из public-документов, проверяет FX, ссылки, суммы, период, IDs и баланс. Возврат должен быть обеспечен прошлыми поступлениями; будущий платёж его не оправдывает. Проверяющий не импортирует генератор и не читает provenance.
- `generation/scenario.py`: четыре настраиваемых семейства duplicate_invoice/payment_allocation/fx_mismatch/period_cutoff, до 12 меток. Сначала проверяется clean-история, каждое изменение имеет before/after. FX-mode rate/date; allocation-mode partial/missing. Документы и правильные FX-цены не меняются.
- Две причинные композиции: fx_allocation применяет распределение к уже неверно оценённой сумме того же платежа; duplicate_cutoff переносит всю пачку из четырёх строк дублированного счёта в другой период. Counts включают эти метки, не добавляют скрытых ошибок сверх конфигурации.
- `domain/findings.py`: строгие Issue/Truth/Finding/Submission, canonical case-sensitive ID sets. Отдельные повторные находки остаются и считаются FP.
- `evaluation/truth.py`: верифицирует полный эталон только по открытым записям, восстанавливает чистую книгу и требует достаточных доступных evidence sets. Необъяснённое расхождение отвергается. Для FX и allocation суммы выражены в базовой валюте.
- `evaluation/scoring.py`: максимальное matching один к одному, TP/FP/FN/P/R/F1, общая награда `clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)`. Полная evaluate_submission сначала проверяет truth; внутренний score_submission предполагает уже проверенный эталон. Невалидная отправка получает -1, плохой приватный эталон является ошибкой хозяина.
- `generation/storage.py`: шесть public-файлов отдельно от truth/provenance; public-reader не читает private. Есть supervisor-only load_scenario с проверкой truth. Новую папку создаёт без перезаписи существующей; private-права 0700/0600 не заменяют sandbox.
- `environment/core.py`: development AuditEnv reset/step и list_records/get_record/get_document/calculator/submit. Бюджеты, стабильные table cursors, копии наблюдений, bounded errors, JSON-action cap 512 KiB, закрытие на timeout/step limit. При evaluation политике выдаётся reward=0 и пустой info, host получает итог через evaluation_result после завершения.
- `environment/calculator.py`: AST + Decimal, без eval/вызовов/файлов; 256 символов, 64 узла, 12 уровней и числовые границы.
- `evaluation/demo.py`: evaluator-only oracle запрашивает реальные evidence инструментами, включая таблицу fx, отправляет findings и сохраняет trajectories/summary. Это integration/ceiling test, не качество агента или обучение.
- `policies/baselines.py`: random с отдельным policy seed, flag-all (до 30 обвинений в дублях), независимая reconciliation по агрегатам документов/проводок. Только JSON-копии наблюдений, страницы до 50 строк, резерв submit; неполные данные/tool errors → воздержание. Нет импорта generation/environment/evaluation и чтения файлов; используется публичный Decimal-примитив domain. Это доверенный код в одном процессе, не OS sandbox.
- `evaluation/benchmark.py`: пять development-профилей, одинаковые seed/config для всех четырёх стратегий; oracle остаётся host-only. SHA-256 public-записей, конфиги, версии, метрики, TP/FP/FN по семействам, причины неуспешных прогонов, JSON/Markdown-отчёты и JSONL-траектории. Все детерминированные поля и траектории повторяются; runtime измеряется отдельно после reset.
- CLI: doctor, info, generate-clean, validate-clean, generate-scenario, validate-scenario, score, demo, benchmark. info показывает development_baseline_benchmark, end_to_end_available=true и security_mode=development_in_process.

## Что НЕ готово

- В 0.4.0 реализованы и проверены в Linux CI JSON-line IPC, worker и Docker-backend: без host mounts/сети, read-only root, UID65534, cap-drop/no-new-privileges, CPU/RAM/PID/FD/tmpfs-лимиты, cleanup. Docker обязателен по умолчанию, fallback нет. Локально Docker отсутствует, sandbox-exec запрещён средой. Development subprocess и прежние demo/benchmark не являются OS-sandbox. Контейнеры доверяют ядру/движку; это не microVM. Образ пока собирается с Python-тега, pin digest остаётся для упаковки.
- Политики и development failure analysis работают, но это узкие правила для синтетической модели, без LLM и обучения. Счета в иностранной валюте, multi-invoice receipts и новые ошибки не входят в проверенный охват reconciliation. Oracle не является независимым агентом.
- Наборы 10 train + 10 dev, независимый conformance harness и source/wheel builder готовы; финальный CI комплекта ещё проверяется. Наши тесты нельзя называть официальным стендом организаторов.
- MIT добавлена по выбору пользователя. requirements.lock пустой (stdlib runtime/test), requirements-build.lock фиксирует setuptools79.0.1+wheel hash. Счета в иностранной валюте, нераспределённые поступления и переоценка валютных остатков не моделируются; это ограниченный синтетический мир.

## Конфиги и точные определения

- `configs/clean.json`: прежний clean v0.1, одна валюта, без новых граничных случаев/возвратов.
- `configs/scenario.json`: прежние два семейства v0.1. Старые файлы принимаются в прежней форме; новые функции не включаются молча.
- `configs/full.json`: v0.2, четыре независимых семейства, 60 счетов, 12 счетов с иностранными поступлениями, четыре граничных случая и четыре возврата.
- `configs/interactions.json`: та же чистая история и четыре семейства, обе композиции.
- `configs/default.json`: неиспользуемый проект первоначального полного формата; не передавать его текущим генераторам.
- Определения expected_amount/affected_ids/evidence и декомпозиция взаимодействий — `docs/ISSUES.md`. Форматы — `docs/DATA.md`, API — `docs/ENVIRONMENT.md`, проверки — `docs/CHECKPOINTS.md`.
- Пакет — 0.5.0, но generator_version и scenario_generator_version остаются 0.2.0: алгоритмы генерации не менялись. Инъекции — injections-v2. Seed/config без версии алгоритма недостаточны для повторения старой версии.

## Проверки и исправленные ошибки

UI: `make check` — 154 теста, 149 проходят, 5 skipped. 7 новых view/routing-проверок проходят; один настоящий HTTP-тест локально skip из-за запрета socket.bind, в CI такой запрет считается ошибкой. JS app.js/samples.js синтаксически проверен Node VM. Chrome открыл локальный index.html и показал первый экран (скриншот) и наполненный AX с 4 находками, TP4/FP0/FN0 и реальными документами. Последующие клики/resize через native CUA нестабильны (noWindowsAvailable/guard); mobile viewport и диалоги визуально не подтверждены. Не заявлять их QA пройденным. Документация — `docs/UI.md`.

UI опубликован в main коммитом `e2182afa0f6c8a116157e7d8cdb9b065feddc23a`, origin/main обновлён fetch. CI 43573464612 success: обычный набор выполняет настоящий LiveHTTPTests, отдельная job — 4 контейнерных теста, Node --check проверяет app.js/samples.js. На Linux суммарно 154 различные проверки, на Mac HTTP и Docker по-прежнему недоступны. Локальный HEAD/index всё ещё старый из-за защищённой .git; не переписывать историю и не считать уже опубликованные изменения новыми. Публичный хостинг не создавался, оригинальный hyperstudio.org-DESIGN.md не изменён и не публиковался.

Этап 0.4.0: `make check PYTHON=.venv/bin/python` — 146 найденных тестов, 142 проходят, 4 реальные Docker-проверки локально пропущены. Проверены frames, размеры, UTF-8, NaN/duplicate keys, request_id, EOF, зависания, не читающий stdin worker, stderr-флуд, cleanup процесса, отсутствие fallback/host-env. Внешний reconciliation на interactions seed42: TP4/FP0/FN0, 12 действий, reward0.978; траектория совпадает с in-process политикой. Артефакты: `artifacts/checkpoint-external-worker-2026-11-14`. Исправлен PermissionError от killpg уже завершившейся группы в nested macOS sandbox; неудача завершения живого процесса не игнорируется. Документация — `docs/ISOLATION.md`. В Linux CI будут проверены host/evaluator/network, UID/caps/no-new-privileges, cgroup, полный эпизод и удаление зависшего контейнера.

На этапе 0.3.0 проходили 130 тестов; этапы 0.1/0.2 — 42/87/118. Текущие 142 обычные проверки включают все предыдущие регрессии; ещё 4 теста выполняются только при явном включении Docker.

- Воспроизведены и исправлены два сбоя: крайние даты могли вызвать OverflowError, malformed submit без params не завершал эпизод. `test_regressions.py` сначала упал на обоих случаях, после исправления проходит.
- Чистые FX/границы и независимые/составные четыре семейства проверены на 50 seed, неверная FX-дата на 20, возвраты на 20.
- Проверены 16 комбинаций включения семейств, общий максимум 12 меток, causal before/after replay, доступность доказательств, FP/abstention/duplicates/flag-all, ID/order-пары, лимиты времени/шагов и evaluation masking.
- Ручные случаи, не созданные генератором: частичные платежи, одинаковые суммы на разных счетах, валютная разница в minor units, обратный cutoff и корректный/чрезмерный возврат.
- Рабочий прогон 0.2.0 seed 42: `artifacts/checkpoint-four-families-refunds-2026-11-13`, config interactions.json. TP=4, FP=0, FN=0, F1=1, 12 действий, 11 inspection steps, reward=0.978. Независимая проверка с диска ok=true, FX-доказательства прочитаны без ошибок. Артефакты не публикуются.
- Прежний прогон двух семейств: `artifacts/checkpoint-episode-2026-11-13`, TP=2, 11 действий, reward=0.98. Чистый исходный пример: `artifacts/checkpoint-clean-2026-11-13`, 50 счетов, 66 платежей, 232 проводки.
- Benchmark 0.3.0: `artifacts/checkpoint-baselines-2026-11-14`, seeds 42–51, policy seed 0; 50 эпизодов, 200 прогонов, 140 меток, 10 чистых компаний. Reconciliation/oracle: TP140/FP0/FN0; random: TP0/FP200/FN140; flag-all: TP22/FP1478/FN118. Reconciliation mean reward0.9788, 11.6 шага; oracle0.9776, 12.2 (отдельные evidence requests вместо страниц). Подробности и ограничения — `docs/BASELINES.md`.
- Добавлены 9 тестов политик и 3 benchmark: ручная композиция четырёх ошибок без генератора, opaque IDs/курсоры, разные валюты, 12 меток, reserve-submit, tool errors, локальный RNG, повторы отчётов/траекторий, hash экспортированных данных, отсутствие закрытых полей, CLI/no-overwrite.
- Аудит перед перерывом 14 ноября: повторно прошли 130 тестов; ещё 100 development-эпизодов / 400 прогонов, новые episode seeds 100–119, policy seed 17. Все 400 submissions валидны и повторно оценены с диска с точным совпадением метрик; нет tool errors/truncation, шагов не больше 100, evaluation rewards скрыты, приватные поля в наблюдениях не обнаружены. Reconciliation/oracle: TP280/FP0/FN0, все 20 чистых компаний без ложных тревог. Диапазон размеров в этом прогоне: 219–293 проводки и 108–150 документов, в пределах ориентиров черновика. Три CLI demo и validate-scenario прошли. Артефакты: `artifacts/audit-2026-11-14-9yc9t07a/`, краткий итог — `audit-summary.json`.
- Чистый снимок `git archive HEAD` отдельно запущен в temp с Python `-S` (без site-packages/editable установки): doctor/info, generate-clean/validate-clean, interactions demo/validate-scenario успешны. Локальная история чата, venv и старые артефакты в снимок не попали. Это проверка запуска исходников, не сборки wheel/контейнера и не лимитов CPU/RAM.

## Окружение и GitHub

- `.venv` содержит Python 3.11.18; активировать `source .venv/bin/activate`. Его interpreter находится в `.tools/python`, этот каталог нужен для работы venv. Системный Python 3.9.6 не менялся.
- Пакет был установлен editable; модуль и CLI используют исходники 0.4.0, метаданные прежней editable-установки могут оставаться 0.3.0 до переустановки. Runtime-зависимостей нет. uv 0.13.8 — `.tools/uv/bin/uv`; .tools/.cache/.venv исключены из Git.
- GitHub-плагин подключён как larl9n, чтение и запись уже доказаны публикациями. Сеть терминала зависит от sandbox-разрешений текущего сеанса. Не требовать повторного подключения плагина.
- Для публикаций используются GitHub tree/commit/ref с expected_sha и force=false, затем fetch/read-tree/update-ref для локальной синхронизации. GitHub назначает автора аккаунта; вымышленные имя/email не настраивать. Обычный терминальный push отдельно не проверен, gh отсутствовал при последней проверке.
- Версия 0.3.0, коммит `7c52405`, опубликована в main и прошла [CI на 130 тестах](https://github.com/larl9n/genesis-hackaton/actions/runs/43488828003); повторно подтверждено при аудите. На начало аудита локальная main совпадала с удалённой и рабочее дерево было чистым. Итоги аудита и эти дополнения к контексту сохранены локально; код в этом аудите не менялся. При следующей публикации включить обновлённый контекст.
- .git защищена от обычной записи; для служебных изменений использовать доступный механизм разрешений, не обходить защиту и не использовать force push. Историю remote читать перед публикацией.
- Версия 0.4.0 опубликована коммитом `42b10f676d5d5d27c7ff68d84a0823090b7b7981`. [CI 43570935768](https://github.com/larl9n/genesis-hackaton/actions/runs/43570935768): scaffold и isolated-worker success; журнал Docker job 132374954780 подтверждает `Ran 4 tests ... OK`, полный эпизод, реальные запреты и cleanup. Проверенный CI worker image ID: `sha256:4de36b6e7d78a36bfefe680642f437ac9e6758fdd6201171430fb6259c02ea4c` (не переносимый base-image digest).
- `git fetch origin` обновил origin/main до 42b10f6. Обновление локальной main через `git update-ref` запрещено текущей файловой песочницей (Operation not permitted); обход не применялся. Локальные исходники соответствуют опубликованному коду, но HEAD/index пока остались на 7c52405 и изменения видны как незакоммиченные. До следующих публикаций сравнивать файлы с актуальным origin/main, а не считать весь diff новым; синхронизация refs требует разрешённого механизма или действия пользователя в обычном терминале. Состояние не исправлять force/reset с удалением файлов.
- Документация с подтверждением результатов опубликована следующим коммитом `993d80c7cae76acab1fbaea48a56725ba8697db0`; origin/main получен через fetch. Его повторный [CI 43571265966](https://github.com/larl9n/genesis-hackaton/actions/runs/43571265966) также завершился success. Локальная main остаётся на 7c52405 по указанной причине; только эта итоговая запись контекста сделана после последней публикации.

## Как вернуться к чату

Проверено в codex-cli 0.169.0; в обычном терминале:

```bash
codex resume 01a1d536-8ebb-7251-9871-1d3b095ddd0b -C /Users/zhopa/genesis-fintech-env
```

Список всех сеансов — `codex resume --all`. `--last` может открыть другой чат. Возврат зависит от наличия локального сеанса. Новый чат в этой папке прочитает AGENTS.md и этот файл; локальный CHAT_HISTORY.md — снимок видимой переписки, не публичный файл.

## Следующий этап

UI реализован и опубликован; HTTP/API подтверждены CI, desktop просмотрен. Полный mobile/dialog visual QA остаётся непроверенным из-за ограничений CUA. Основной roadmap реализован: 10 train + 10 dev, MIT/lockfile/pinned image, cgroup counters, source/wheel и offline verifier. Финальный CI 0.5.0 ещё проверяется. После его успеха нужны формат/время приёма организаторов и само выступление/отправка. Генератор, baseline/benchmark, IPC и контейнерный worker не начинать заново. Прежний benchmark и UI-run остаются in-process; не выдавать их за изолированную оценку или обучение.

## Блоки C/D, 14 ноября

C прошёл [CI 43588561164](https://github.com/larl9n/genesis-hackaton/actions/runs/43588561164), commit a5d0fffbf2aa7591b248a76785688fb93f8ab88e: четыре реальные Docker-интеграции, 80 runs/80 replays/20 grader-пар. Worker cgroup peak 25 141 248 bytes, supervisor RSS 30 412 800, CLI RSS 29 290 496; max worker elapsed <0.376s, весь suite 53s. Все 60 основных worker counters проверены и все повторы тоже. Измерение не включает daemon/ядро, физический хост 2 CPU/4GB не сертифицирован.

D: scripts/build_release.py, verify_release.py, tests/test_release.py, LICENSE, requirements*.lock, docs/RELEASE.md/RESOURCES.md/DEMO.md. Source allowlist исключает CHAT_HISTORY/private/artifacts; манифест hashes, normalized tar/gzip и SOURCE_DATE_EPOCH для wheel. Чистый venv без package downloads запускает установленный CLI с -I вне repo и demo TP4/FP0/FN0, затем все тесты распакованного source. Локальный probe прошёл; итоговая сборка и CI ещё проверяются. UI samples перезаписаны только для версии engine 0.5.0, дизайн не менялся. Base image закреплён digest a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39. Старая editable metadata .venv может оставаться 0.3.0; wheel отдельно проверяется на 0.5.0.
