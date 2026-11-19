# TEMP: reports_temp — как удалить фичу

Временная фича PDF-отчётов по выборке сырья. Удаляется целиком (общий этап 15 плана).
Новых таблиц и миграций нет, другие фичи на неё не ссылаются.

1. Удалить папку `features/reports_temp/` (вместе с `infra/fonts/`).
2. В `routes.py` убрать две строки с меткой `TEMP: reports_temp` (импорт и `include_router`).
3. В `requirements.txt` убрать блок `# TEMP: reports_temp` (`reportlab`, `pillow`).
4. В `.importlinter` убрать `features.reports_temp` из `containers` и контракт
   `reports-temp-isolated` (помечен `TEMP`).
5. Удалить `tests/test_reports_temp.py`.
6. Перегенерировать снимок OpenAPI: `UPDATE_OPENAPI_SNAPSHOT=1 python -m unittest tests.test_openapi_snapshot`
   (результат должен совпасть со снимком до фичи).
7. Убрать раздел о временной фиче в `docs/backend/README.md`.
8. Проверить: `grep -ri "reports_temp\|reports-temp\|TEMP: reports" .` ничего не находит;
   `ruff check .`, `lint-imports`, тесты проходят.

Изменений в Dockerfile не делалось: шрифты лежат внутри папки фичи.
Шрифт DejaVu Sans распространяется по свободной лицензии (Bitstream Vera / DejaVu).
