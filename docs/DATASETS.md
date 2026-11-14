# Публичные train/dev-наборы v1

Замороженный корпус — 10 train + 10 dev, по две чистые компании в каждом наборе. Всего 72 метки: по 36 в train/dev; четыре семейства и обе композиции. Размеры: 262–299 проводок и 135–150 документов. Варьируются пять базовых валют, FX-разрядности, часовые пояса, split/partial/refund, режимы FX и распределения. Dev использует другие seed и новые сочетания параметров.

`datasets/public-v1.tar.gz` содержит только открытые записи: 120 файлов эпизодов и index.json. Контрольные суммы — `datasets/public-v1.index.json`. В архиве нет truth, provenance, seed или конфигураций инъекций. Рецепт публичных наборов — `configs/dataset.json`; это public train/dev, не секретный held-out тест. Рецепт не передаётся политике.

```bash
PYTHONPATH=src python -m genesis_fintech generate-dataset --spec configs/dataset.json --output artifacts/public-corpus-v1
PYTHONPATH=src python -m genesis_fintech validate-dataset artifacts/public-corpus-v1 --replay
```

Каталог результата должен быть новым. Структура:

```text
dataset.json                  # supervisor-only: полный рецепт, seed и hashes
public-index.json             # только episode IDs и hashes открытых файлов
public-train-dev.tar.gz        # экспорт только public
episodes/train/<episode_id>/public + private
episodes/dev/<episode_id>/public + private
```

Наличие соседней private-папки не обеспечивает изоляцию; worker ничего из этого не монтирует. Закрытые служебные файлы остаются локально у оценщика. Права private 0700/0600 и dataset.json 0600 не заменяют Docker.

Валидация проверяет строгую форму рецепта, размеры и разделение наборов, отсутствие повторных seeds/IDs, SHA-256 всех файлов, версии алгоритмов, число типов ошибок, независимую проверку truth по публичным записям и корректность public-экспорта. Символические ссылки и произвольные пути отвергаются. `--replay` дополнительно воспроизводит каждую компанию из seed/config/version и сравнивает данные, эталон и provenance. Простой validate не вызывает генератор.

Архив и все файлы побайтово воспроизводятся при том же зафиксированном runtime/алгоритме. Временные метки, владельцы и порядок tar-нормализованы. SHA-256 текущего публичного архива: `408c1cef6dc2257879d4b441f046642d0de1553c570129207401e83c68984e50`.
