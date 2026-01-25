#!/bin/bash
# Настройка сервера для деплоя через Git
# Запускается один раз при первой настройке

set -e

SERVER_IP="87.247.157.122"
SERVER_USER="root"
PROJECT_DIR="/opt/wed-bobry-bot"
REPO_URL="https://github.com/Alex-Bychenkov/wed-bobry-bot.git"

echo "🔧 Настройка Git-деплоя на сервере..."

ssh "$SERVER_USER@$SERVER_IP" << ENDSSH
set -e

# Устанавливаем Git если не установлен
if ! command -v git &> /dev/null; then
    echo "📦 Установка Git..."
    apt-get update && apt-get install -y git
fi

# Бэкапим текущий .env если есть
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" /tmp/bot-env-backup
    echo "✅ .env сохранён"
fi

# Бэкапим данные если есть
if [ -d "$PROJECT_DIR/data" ]; then
    cp -r "$PROJECT_DIR/data" /tmp/bot-data-backup
    echo "✅ data/ сохранена"
fi

# Клонируем репозиторий
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "📂 Репозиторий уже инициализирован"
    cd "$PROJECT_DIR"
    git fetch origin
    git reset --hard origin/main
else
    echo "📥 Клонирую репозиторий..."
    rm -rf "$PROJECT_DIR"
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# Восстанавливаем .env
if [ -f /tmp/bot-env-backup ]; then
    mv /tmp/bot-env-backup "$PROJECT_DIR/.env"
    echo "✅ .env восстановлен"
fi

# Восстанавливаем данные
if [ -d /tmp/bot-data-backup ]; then
    rm -rf "$PROJECT_DIR/data"
    mv /tmp/bot-data-backup "$PROJECT_DIR/data"
    echo "✅ data/ восстановлена"
fi

echo ""
echo "✅ Сервер настроен для Git-деплоя!"
echo "Теперь деплой можно запускать через GitHub Actions"

ENDSSH
