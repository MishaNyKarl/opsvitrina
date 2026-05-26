# Правила разработки и деплоя

## Рабочий процесс

1. Все новые изменения сначала делаем и пушим в ветку `staging`.
2. GitHub Actions автоматически деплоит `staging` на тестовый домен:
   `https://stagingopsvitrinaru.lol`
3. Проверяем изменения на staging.
4. Только после проверки переносим изменения в `main`.
5. Production деплоится вручную из `main`.

## Как залить staging в production

Локально в проекте:

```powershell
git checkout staging
git pull origin staging

git checkout main
git pull origin main

git merge staging
git push origin main
```

После этого в GitHub:

1. Открыть репозиторий `MishaNyKarl/opsvitrina`.
2. Перейти в **Actions**.
3. Выбрать workflow **Deploy production**.
4. Нажать **Run workflow**.
5. Выбрать ветку `main`.
6. В поле `confirm` написать `deploy`.
7. Запустить workflow.

## Проверка после production deploy

Проверить основной домен:

```text
https://read.lifestoruhabstt.info
```

Если визуальные изменения не появились, сначала обновить страницу через `Ctrl+F5`.

## Важное правило

Не править production руками на сервере. Код должен попадать в production только через:

```text
staging -> проверка -> merge в main -> Deploy production
```
