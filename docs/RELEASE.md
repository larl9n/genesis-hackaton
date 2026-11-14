# Сборка и проверка комплекта 0.6.0

Для запуска из исходников достаточно Python 3.11; runtime и тесты не требуют сторонних библиотек. Docker нужен для изолированной оценки. Интернет требуется на этапе подготовки Python/build tools и загрузки базового образа, затем оценивание работает без загрузок; worker всегда запускается с `--network=none --pull=never`.

## Подготовка до отключения сети

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip download --require-hashes --only-binary=:all: --no-deps -r requirements-build.lock -d artifacts/wheelhouse
.venv/bin/python -m pip install --no-index --find-links artifacts/wheelhouse --require-hashes --no-deps -r requirements-build.lock
docker build -f docker/worker.Dockerfile -t genesis-audit-worker:0.6.0 .
```

`requirements.lock` фиксирует пустое множество runtime/test-зависимостей. `requirements-build.lock` фиксирует проверенный setuptools 79.0.1 и SHA-256 universal wheel по [PyPI JSON](https://pypi.org/pypi/setuptools/79.0.1/json). Он нужен только для wheel. Наша сборка source bundle использует собственный allowlist и не применяет setuptools sdist/MANIFEST exclusions.

Python base image закреплён digest `a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39`, подтверждённым успешной сборкой Linux CI. Во время каждого оценивания образ дополнительно закрепляется локальным immutable image ID. Для переноса без registry можно заранее выполнить `docker save genesis-audit-worker:0.6.0 -o worker-image.tar`, на другом хосте — `docker load -i worker-image.tar`.

## Сборка и чистая проверка без package downloads

```bash
.venv/bin/python scripts/build_release.py --output dist/release-v0.6.0
.venv/bin/python scripts/verify_release.py dist/release-v0.6.0 --full-check
```

Каталог output должен быть новым. Получаются source `genesis-fintech-env-0.6.0.tar.gz`, устанавливаемый wheel и `SHA256SUMS`. В source bundle есть исходники, тесты, конфиги, документация, LICENSE, UI и public train/dev. Встроенный SOURCE-MANIFEST.json фиксирует каждый файл. Владельцы, порядок, modes, gzip/tar timestamps нормализованы. Wheel собирается с SOURCE_DATE_EPOCH=0; повтор проверяется по SHA-256 в CI. Это повторяемость в фиксированном Python/build окружении, не обещание одинакового gzip для любых версий zlib.

Проверка сначала сверяет hashes и состав архива, затем создаёт новое venv через встроенный ensurepip и ставит wheel с `--no-index --no-deps`. CLI запускается с `-I` вне репозитория, demo должен получить TP4/FP0/FN0. `--full-check` дополнительно запускает все тесты из распакованных исходников. Реальные Docker-тесты включаются отдельной командой `GENESIS_RUN_DOCKER_TESTS=1 PYTHONPATH=src python -m unittest discover -s tests -p test_container.py -v` после сборки image.

## Одна команда для полного оценивания

```bash
make evaluate PYTHON=.venv/bin/python RUN_DIR=artifacts/submission-check
```

Команда генерирует host-only корпус, сравнивает public index и архив с замороженными данными, запускает Docker-оценку с повторением. Нужен новый RUN_DIR. Итог: report.json/report.md, conformance.json и траектории. Oracle остаётся привилегированной проверкой оценщика. Не передавайте недоверенной политике source recipe, private corpus или полный report через mounts.

CI проверяет pinned image, реальную изоляцию, полный корпус, ресурсы и чистый комплект. Release source/wheel и оценочные отчёты сохраняются как Actions artifacts. Они не являются автоматической отправкой организаторам.

С версии 0.6.0 source bundle дополнительно содержит examples/training-v1: начальные наблюдения, полный trajectories.jsonl и manifest. Offline verifier установленного wheel воспроизводит корпус и train-траектории и сравнивает их с вложенным примером; CI повторяет эту проверку. Матрица требований и границы приёмки — SUBMISSION.md, контракт train data — TRAINING.md.

Ограничения: публичный синтетический корпус, узкие rule-based политики, без обучения весов и без результатов официального стенда. Подробности качества — BASELINES.md и CONFORMANCE.md; измерения — RESOURCES.md. Mobile/dialog visual QA остаётся отдельной задачей UI.
