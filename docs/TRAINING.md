# Обучающие траектории

`collect-trajectories` сохраняет действия обычной политики и награды режима `train` на десяти замороженных train-эпизодах. Dev не используется для rollout; целостность всего исходного корпуса проверяется. Это подготовка данных взаимодействия со средой, без обновления весов модели.

```bash
PYTHONPATH=src python -m genesis_fintech collect-trajectories artifacts/public-corpus-v1 --output artifacts/train-rollouts
PYTHONPATH=src python -m genesis_fintech validate-trajectories artifacts/public-corpus-v1 artifacts/train-rollouts
```

Папка output должна быть новой. `--policy` принимает reconciliation, random или flag-all; `--policy-seed` по умолчанию 17. Oracle не допускается. Экспорт выполняется доверенным кодом supervisor в одном процессе; он не предназначен для произвольного недоверенного агента. Docker-оценка остаётся отдельным режимом.

## Файлы и переходы

- `initial_observations.jsonl`: episode_id и начальное observation, полученное из reset.
- `trajectories.jsonl`: episode_id, step, action, observation, reward, terminated, truncated. Observation — ответ после действия, как в остальных траекториях проекта. Для первого перехода исходное состояние берётся из initial_observations; для следующих — из предыдущего ответа.
- `manifest.json`: формат, версия engine, policy/policy_seed, split, fingerprints публичных записей, hashes файлов, число шагов и return каждого эпизода. Здесь нет seed генератора, private truth или scorer diagnostics.

Промежуточные reward равны нулю. Только последний переход режима train получает общую терминальную награду. В evaluation та же последовательность действий по-прежнему видит reward=0. Начальные наблюдения и JSONL содержат только публичные данные; они не включают truth/provenance и описания скрытых допустимых evidence sets.

`validate-trajectories` независимо проверяет корпус, восстанавливает каждое начальное состояние по сохранённым записям, повторяет действия и сравнивает ответы, награды и завершение. Он также повторяет заявленную детерминированную политику, чтобы ошибочная метка policy не прошла проверку. Генератор при replay не вызывается. Подделанный reward не становится допустимым после переписывания hash.

## Готовый пример

`examples/training-v1/` включён в source bundle: 10 train-эпизодов reconciliation, 120 переходов, mean return 0.978, без усечения. Все три файла воспроизводятся побайтово. Перед проверкой примера восстановите host-only корпус через generate-dataset, затем выполните:

```bash
PYTHONPATH=src python -m genesis_fintech validate-trajectories artifacts/public-corpus-v1 examples/training-v1
```

Пример содержит публичные синтетические документы и действия, поэтому не является отложенным тестом. Его качество не доказывает обучение или перенос на реальные книги. Для настоящего обучения и оценки обобщения нужен отдельный контролируемый эксперимент, который в обязательный объём кейса не входит.
