# Ops Vitrina

Django-платформа для статей, рекламных потоков, витрин и статистики.

## Локальный запуск

Проект рассчитан на Python 3.11, Django 5.2 и PostgreSQL.

PostgreSQL можно поднять через Docker:

```powershell
docker compose up -d postgres
```

Базовые параметры БД берутся из переменных окружения, с такими значениями по умолчанию:

- database: `opsvitrina`
- user: `opsvitrina`
- password: `opsvitrina`
- host: `127.0.0.1`
- port: `5433`

После установки Python и зависимостей:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py makemigrations
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py createsuperuser
venv\Scripts\python.exe manage.py runserver
```

## Доступ к данным

Основной принцип заложен в `core.models.OwnedModel`:

- администратор видит все;
- менеджер/аналитик видят данные своей команды;
- баер видит только собственные данные.

Для списков в кабинете нужно использовать `Model.objects.visible_for(request.user)`.

## Трекинг

UTM/subid не заводятся как ручные поля управления. Параметры перехода сохраняются в `VisitEvent.query_params`, а конверсии/лиды принимаются через будущий postback endpoint в `PostbackEvent.raw_payload`.
