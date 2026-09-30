# API проверки материалов

Базовый адрес: `http://localhost:8000` после локального запуска или `https://tutor-assistant.lenyldes.ru` на публичном стенде. Авторизации нет. Интерактивную схему найдёте по `/docs`, машиночитаемую OpenAPI‑схему — по `/openapi.json`.

API содержит три операции:

| Метод и путь | Назначение | Успех |
| --- | --- | --- |
| `POST /api/checks` | Проверить набор файлов и сохранить результат | 200, полный результат |
| `GET /api/checks` | Получить историю проверок | 200, массив записей |
| `GET /api/checks/{check_id}` | Получить сохранённые детали | 200, полный результат |

Готовые синтетические файлы лежат в [`demo_files/`](../demo_files/README.md). **Публичное демо доступно всем: не отправляйте персональные данные детей.** Имена файлов и результаты остаются в истории, хотя сами байты файлов не сохраняются.

## `POST /api/checks`

Тело запроса — `multipart/form-data`:

| Поле | Тип | Правило |
| --- | --- | --- |
| `record_type` | строка | Обязательное: `daily` или `weekly` |
| `files` | файл, повторяемое поле | Нужен хотя бы один файл; каждый отправляется отдельной частью с ключом `files` |

```bash
curl --fail-with-body -sS -X POST http://localhost:8000/api/checks \
  -F record_type=daily \
  -F 'files=@demo_files/дневник_наблюдений.xlsx' \
  -F 'files=@demo_files/отчёт_о_занятии.pdf' \
  -F 'files=@demo_files/обратная_связь_родителя.docx'
```

Запускайте команду из корня репозитория после `docker compose up --build`. Для публичного стенда просто замените базовый адрес; используйте только синтетические файлы.

Пример ответа для полного `daily` (ID и время условные, размеры соответствуют файлам в репозитории):

```json
{
  "check_id": "11111111-1111-4111-8111-111111111111",
  "record_type": "daily",
  "status": "complete",
  "status_label": "Запись полная — можно передавать в анализ",
  "reason": "",
  "issues": [],
  "documents": [
    {"name": "дневник_наблюдений.xlsx", "detected_type": "observation_diary", "size_kb": 2},
    {"name": "отчёт_о_занятии.pdf", "detected_type": "lesson_report", "size_kb": 1},
    {"name": "обратная_связь_родителя.docx", "detected_type": "parent_feedback", "size_kb": 1}
  ],
  "extracted": {},
  "checked_at": "2026-09-30T12:00:00Z"
}
```

В поле `documents` попадают **все** присланные файлы в порядке загрузки — в том числе непригодные. `detected_type` — одна из четырёх категорий (`observation_diary`, `lesson_report`, `parent_feedback`, `specialist_conclusion`) либо `null`. `size_kb` — размер в КиБ, округлённый вверх; у пустого файла будет 0. `issues` — массив объектов с полями `level` (`warning` или `error`) и русским `message`. `extracted` всегда `{}`: содержимое документов не извлекается. `checked_at` — время завершения проверки; пока проверка идёт, там `null`.

Статус `complete` значит, что все обязательные категории закрыты пригодными файлами. `incomplete` — если не хватает хотя бы одной обязательной категории. Статус `check_in_progress` можно увидеть в параллельном запросе к истории или деталям, пока обработка идёт. Поле `reason` кратко перечисляет недостающие категории либо остаётся пустым для полного комплекта. Пустой набор файлов вернёт HTTP 400; отсутствующий или неверный `record_type` — HTTP 422. Такие запросы не создают запись.

## `GET /api/checks`

```bash
curl --fail-with-body -sS http://localhost:8000/api/checks
```

Ответ — массив записей от новых к старым. До первой проверки будет `[]`. Каждая запись выглядит так:

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "created_at": "2026-09-30T12:00:00Z",
  "record_type": "daily",
  "status": "complete",
  "materials_count": 3
}
```

`materials_count` учитывает все загруженные файлы — в том числе нераспознанные и с недопустимым форматом. Пока проверка в работе, статус может быть `check_in_progress`, а число уже сохранённых материалов — 0.

## `GET /api/checks/{check_id}`

Возьмите `check_id` из ответа POST либо `id` из истории и подставьте в путь:

```bash
curl --fail-with-body -sS http://localhost:8000/api/checks/11111111-1111-4111-8111-111111111111
```

UUID в примере условный — замените его на реальный ID. Ответ имеет ту же структуру, что и у POST, и читается из PostgreSQL. Неизвестный корректный UUID вернёт HTTP 404 с `{"detail":"Проверка не найдена"}`; неверный формат UUID — HTTP 422. Пока обработка идёт, в деталях будет статус `check_in_progress`, пустые `issues` и `documents`, `extracted: {}` и `checked_at: null`.

## Проверка ошибок через curl

Пустой набор файлов:

```bash
curl -i -sS -X POST http://localhost:8000/api/checks -F record_type=daily
```

Ожидается HTTP 400 и `{"detail":"Добавьте хотя бы один файл"}`.

Неверный тип записи:

```bash
curl -i -sS -X POST http://localhost:8000/api/checks \
  -F record_type=monthly \
  -F 'files=@demo_files/дневник_наблюдений.xlsx'
```

Ожидается HTTP 422: FastAPI вернёт объект `detail` с диагностикой валидации. После обоих запросов история не должна пополниться. Примеры для недостающих категорий, неизвестного имени, недопустимого формата, пустого файла и границы в 20 МиБ собраны в [таблице образцов](../demo_files/README.md).

## Проверка в Postman

1. Импортируйте OpenAPI‑схему по адресу `http://localhost:8000/openapi.json` или `https://tutor-assistant.lenyldes.ru/openapi.json` как коллекцию запросов. [Инструкция Postman по импорту OpenAPI](https://learning.postman.com/docs/integrations/available-integrations/working-with-openAPI/).
2. Для `POST /api/checks` выберите тело **form-data**. Добавьте текстовое поле `record_type` со значением `daily` и несколько строк с одинаковым ключом `files`; у каждой строки выберите тип **File** и свой файл из `demo_files/`. Заголовок `Content-Type` с boundary Postman подставит сам при отправке формы.
3. Отправьте запрос и скопируйте `check_id` из JSON. Выполните `GET /api/checks`, затем `GET /api/checks/{check_id}`, подставив полученный ID. Сравните сохранённый результат с ответом POST.

Для ручной проверки без Postman и curl откройте [демонстрационную страницу](https://tutor-assistant.lenyldes.ru/) либо локальный `/`: четыре кнопки отправляют реальные запросы к тому же API и сразу показывают полученный JSON.
