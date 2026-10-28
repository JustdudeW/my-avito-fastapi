# Avito Shtuka: примеры CRUD на FastAPI и SQLAlchemy

Учебный проект показывает операции CRUD на объявлениях маркетплейса. FastAPI принимает запросы, SQLAlchemy ORM работает с объектами Python, а Microsoft SQL Server хранит пользователей, объявления и операции покупки.

## CRUD простыми словами

Перед запуском установи SQL Server и ODBC Driver 18 for SQL Server. Создай базу `AvitoClone`. Для Windows Authentication строка подключения задаётся так:

```powershell
$env:DATABASE_URL = "mssql+pyodbc://@localhost/AvitoClone?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&TrustServerCertificate=yes"
```

| Операция | Что делает | HTTP-запрос | SQLAlchemy |
| --- | --- | --- | --- |
| Create | Создаёт запись | `POST` | `db.add(obj)` |
| Read | Читает запись | `GET` | `db.get()` или `select()` |
| Update | Изменяет запись | `PUT` | меняем поля объекта и вызываем `commit()` |
| Delete | Удаляет запись | `DELETE` | `db.delete(obj)` |

Основные примеры находятся в `main.py`, в endpoint-ах `/api/ads` и `/api/users`.

## Как показать CRUD в Swagger

Запусти сервер и открой http://127.0.0.1:8000/docs. Для запросов с телом нажми **Try it out** и отправляй JSON из примеров ниже.

### 1. Create: создать объявление

Endpoint `POST /api/ads`.

```json
{
  "owner_id": 1,
  "title": "Велосипед",
  "text": "В хорошем состоянии",
  "price": 15000,
  "status": "активно"
}
```

В коде создаётся Python-объект `Advertisement`, `db.add(ad)` добавляет его в сессию, `db.commit()` сохраняет запись в базе, а `db.refresh(ad)` получает присвоенный SQL Server идентификатор.

### 2. Read: прочитать объявления

Endpoint `GET /api/ads`. Он возвращает объявления страницами. Например, `page=1`, `limit=6` означает первую страницу, до шести записей. Параметр `search` ищет слова в названии и описании.

```text
/api/ads?search=велосипед&page=1&limit=6
```

Один объект по ID: `GET /api/ads/{ad_id}`. Список пользователей: `GET /api/users`, один пользователь: `GET /api/users/{user_id}`.

### 3. Update: изменить объявление

Endpoint `PUT /api/ads/{ad_id}`. Укажи ID объявления в адресе и отправь все поля:

```json
{
  "title": "Горный велосипед",
  "text": "Исправное состояние, недавно обслужен",
  "price": 18000,
  "status": "активно"
}
```

Программа загружает объявление через `db.get(Advertisement, ad_id)`, меняет его поля и вызывает `db.commit()`.

### 4. Delete: удалить объявление

Endpoint `DELETE /api/ads/{ad_id}`. Укажи ID объявления. Код находит объект через `db.get()`, удаляет его вызовом `db.delete(ad)` и сохраняет изменение через `db.commit()`.

Для пользователей доступны такие же операции: `POST /api/users`, `GET /api/users/{user_id}`, `PUT /api/users/{user_id}`, `DELETE /api/users/{user_id}`.

## Пример создания пользователя

`POST /api/users`:

```json
{
  "name": "Иван",
  "email": "ivan@example.com",
  "phone": "+79990000000"
}
```

ID пользователя из ответа можно использовать как `owner_id` при создании объявления.

## Как работает сессия и commit

`get_db()` открывает SQLAlchemy-сессию на время запроса и закрывает её после ответа. Сессия отслеживает изменения объектов. `commit()` подтверждает их в базе. Если во время покупки возникает ошибка, `rollback()` отменяет все изменения этой покупки.

## Покупка

`POST /api/purchases?advertisement_id=ID&buyer_id=ID` — отдельный пример транзакции: проверяет объявление и баланс, списывает деньги у покупателя, начисляет продавцу, отмечает объявление проданным и сохраняет операцию. `GET /api/transactions?user_id=ID` показывает историю покупок и продаж.

## Локальный запуск

Требуются Microsoft SQL Server, ODBC Driver 18 for SQL Server и доступ Windows-пользователя к базе `AvitoClone`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- Сайт: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Отправка проекта на GitHub

```powershell
git add main.py static README.md requirements.txt .gitignore
git commit -m "Add SQLAlchemy CRUD examples"
git push origin main
```

Не добавляй `.venv`, локальный файл базы или секреты подключения.
