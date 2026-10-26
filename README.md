# Avito Shtuka API

## База данных Microsoft SQL Server

Перед запуском надо скачать SQL Server и ODBC Driver 18 for SQL Server. Создать базу `AvitoClone`, затем задайте строку подключения:

```powershell
$env:DATABASE_URL = "mssql+pyodbc://@localhost/AvitoClone?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&TrustServerCertificate=yes"
```

Таблицы `users` и `advertisements` создаются SQLAlchemy автоматически при старте.

## Запуск в Windows PowerShell

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements.txt
\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

После запуска:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json
