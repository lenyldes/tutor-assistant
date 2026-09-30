# API проверки материалов

Базовый адрес: `http://localhost:8000` после локального запуска или `https://tutor-assistant.lenyldes.ru` на публичном стенде. Авторизации нет. Интерактивная схема доступна по `/docs`, машиночитаемая OpenAPI-схема — по `/openapi.json`.

API содержит три операции:

| Метод и путь | Назначение | Успех |
| --- | --- | --- |
| `POST /api/checks` | Проверить набор файлов и сохранить результат | 200, полный результат |
| `GET /api/checks` | Получить историю проверок | 200, массив записей |
| `GET /api/checks/{check_id}` | Получить сохранённые детали | 200, полный результат |

Готовые синтетические файлы находятся в [`demo_files/`](../demo_files/README.md). **Публичное демо доступно всем: не отправляйте персональные данные детей.** Имена файлов и результаты остаются в истории, хотя сами байты файлов не сохраняются.

## `POST /api/checks`

Тело — `multipart/form-data`:

| Поле | Тип | Правило |
| --- | --- | --- |
| `record_type` | строка | Обязательное: `daily` или `weekly` |
| `files` | файл, повторяемое поле | Хотя бы один файл; каждый отправляется отдельной частью с именем `files` |

```bash
curl --fail-with-body -sS -X POST http://localhost:8000/api/checks \
  -F record_type=daily \
  -F 'files=@demo_files/дневник_наблюдений.xlsx' \
  -F 'files=@demo_files/отчёт_о_занятии.pdf' \
  -F 'files=@demo_files/обратная_связь_родителя.docx'
```

Команду выполняйте из корня репозитория после `docker compose up --build`. Для публичного стенда замените базовый адрес в команде; используйте только синтетические файлы.

Пример структуры ответа для полного `daily` (ID, размеры и время условные):

```json
{
  "check_id": "11111111-1111-4111-8111-111111111111",
  "record_type": "daily",
  "status": "complete",
  "status_label": "Запись полная — можно передавать в анализ",
  "reason": "",
  "issues": [],
  "documents": [
    {"name": "дневник_наблюдений.xlsx", "detected_type": "observation_diary", "size_kb": 1},
    {"name": "отчёт_о_занятии.pdf", "detected_type": "lesson_report", "size_kb": 1},
    {"name": "обратная_связь_родителя.docx", "detected_type": "parent_feedback", "size_kb": 1}
  ],
  "extracted": {},
  "checked_at": "2026-09-30T12:00:00Z"
}
```

`documents` содержит **все** присланные файлы в порядке загрузки, включая непригодные. `detected_type` — одна из четырёх категорий (`observation_diary`, `lesson_report`, `parent_feedback`, `specialist_conclusion`) или `null`. `size_kb` — размер в Киб, округлённый вверх; у пустого файла 0. `issues` — массив объектов с `level` (`warning` или `error`) и русским `message`. `extracted` всегда `{}`: содержимое документов не извлекается. `checked_at` — время завершения проверки; до завершения равно `null`.

Статус `complete` означает, что все обязательные категории представлены пригодными файлами. `incomplete` означает отсутствие хотя бы одной обязательной категории. `check_in_progress` может быть виден в параллельном запросе истории или деталей во время обработки. `reason` кратко перечисляет недостающие категории или пуст для полного комплекта. Пустой набор даёт HTTP 400; отсутствующий или неверный `record_type` — HTTP 422. Такие запросы не создают запись.

## `GET /api/checks`

```bash
curl --fail-with-body -sS http://localhost:8000/api/checks
```

Ответ — массив от новых к старым. До первой проверки — `[]`. Каждая запись содержит:

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "created_at": "2026-09-30T12:00:00Z",
  "record_type": "daily",
  "status": "complete",
  "materials_count": 3
}
```

`materials_count` включает все загруженные файлы, в том числе нераспознанные и запрещённого формата. Пока проверка обрабатывается, её статус может быть `check_in_progress`, а число уже сохранённых материалов — 0.

## `GET /api/checks/{check_id}`

Возьмите `check_id` из ответа POST или `id` из истории и подставьте в путь:

```bash
curl --fail-with-body -sS http://localhost:8000/api/checks/11111111-1111-4111-8111-111111111111
```

Приведённый UUID — пример; для фактического запроса замените его на полученный ID. Ответ имеет ту же схему, что и POST, и читается из PostgreSQL. Неизвестный корректный UUID возвращает HTTP 404 с `{"detail":"Проверка не найдена"}`; неверный формат UUID даёт HTTP 422. Пока обработка продолжается, детали показывают `check_in_progress`, пустые `issues` и `documents`, `extracted: {}` и `checked_at: null`.

## Проверка ошибок через curl

Пустой набор файлов:

```bash
curl -i -sS -X POST http://localhost:8000/api/checks -F record_type=daily
```

Ожидается HTTP 400 и `{"detail":"Добавьте хотя бы один файл"}`.

Неверный тип записи:

```bash
curl -i -sS -X POST http://localhost:8000/api/checks \
  -F record_type=monthly \
  -F 'files=@demo_files/дневник_наблюдений.xlsx'
```

Ожидается HTTP 422. FastAPI возвращает объект `detail` с диагностикой валидации. После обоих запросов история не должна пополниться. Случаи недостающих категорий, неизвестного имени, недопустимого формата, пустого файла и границы 20 МиБ приведены в [таблице образцов](../demo_files/README.md).

## Проверка в Postman

1. Импортируйте OpenAPI-схему по адресу `http://localhost:8000/openapi.json` или `https://tutor-assistant.lenyldes.ru/openapi.json` как коллекцию запросов. [Инструкция Postman по импорту OpenAPI](https://learning.postman.com/docs/integrations/available-integrations/working-with-openAPI/).
2. Для `POST /api/checks` выберите тело **form-data**. Добавьте текстовое поле `record_type` со значением `daily` и несколько строк с одинаковым ключом `files`, у каждой выберите тип **File** и свой файл из `demo_files/`. Заголовок `Content-Type` с boundary Postman выставит при отправке формы.
3. Отправьте запрос, скопируйте `check_id` из JSON. Выполните `GET /api/checks`, затем `GET /api/checks/{check_id}`, заменив параметр на полученный ID. Сравните сохранённый результат с ответом POST.

Для ручной проверки без Postman и curl откройте [демонстрационную страницу](https://tutor-assistant.lenyldes.ru/) или локальный `/`: четыре кнопки создают настоящие запросы к тому же API и показывают полученный JSON.
