# Среда Бобры — Telegram-бот

MVP бота для записи на ближайшую среду в 20:30 с оповещениями, сбором фамилий и итоговым списком.

## Возможности
- Ежедневные оповещения (сб–ср) с кнопками статусов
- Запрос фамилии один раз и сохранение в базе
- Итоговый список обновляется в одном сообщении
- Команды `/start`, `/status`, `/reset`, `/close`

## Настройка окружения
Создайте файл `.env` на основе `.env.example`:
```
BOT_TOKEN=ваш_токен
CHAT_ID=-1001234567890
TIMEZONE=Europe/Moscow
NOTIFY_TIME=10:00
ADMIN_IDS=123456789,987654321
```

## Запуск локально
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Запуск в Docker
```bash
docker build -t wed-bobry-bot .
docker run --env-file .env --name wed-bobry-bot --restart unless-stopped wed-bobry-bot
```

## Docker Compose
```bash
docker compose up --build -d
```

## Автопересборка при изменениях
```bash
docker compose watch
```

## Команды Docker
- Сборка образа: `docker build -t wed-bobry-bot .`
- Запуск контейнера: `docker run --env-file .env --name wed-bobry-bot --restart unless-stopped wed-bobry-bot`
- Просмотр логов: `docker logs -f wed-bobry-bot`
- Остановка контейнера: `docker stop wed-bobry-bot`

## Команды
- `/start` — инструкция для пользователей
- `/status` — текущий список
- `/reset` — сбросить сессию (администратор чата или из `ADMIN_IDS`)
- `/close` — закрыть сессию (администратор чата или из `ADMIN_IDS`)
