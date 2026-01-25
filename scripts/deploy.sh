#!/bin/bash
set -e

SERVER_IP="87.247.157.122"
SERVER_USER="root"
SERVER_PASS="${SERVER_PASS:-F65NkiCBmM}"
PROJECT_DIR="/opt/wed-bobry-bot"
LOCAL_DIR="."

# Определение команды SSH
if command -v sshpass &> /dev/null && [ -n "$SERVER_PASS" ]; then
    SSH_CMD="sshpass -p '$SERVER_PASS' ssh -o StrictHostKeyChecking=no -T"
    SCP_CMD="sshpass -p '$SERVER_PASS' scp -o StrictHostKeyChecking=no"
    RSYNC_CMD="sshpass -p '$SERVER_PASS' rsync -avz -e 'ssh -o StrictHostKeyChecking=no'"
else
    SSH_CMD="ssh"
    SCP_CMD="scp"
    RSYNC_CMD="rsync -avz"
fi

echo "🚀 Развертывание бота Бобры на сервер $SERVER_IP..."

# Проверка наличия .env файла
if [ ! -f "$LOCAL_DIR/.env" ]; then
    echo "❌ Ошибка: файл .env не найден!"
    echo "Скопируйте .env.example в .env и заполните необходимые значения"
    exit 1
fi

# Проверка настройки сервера
echo "🔍 Проверка настройки сервера..."
if ! $SSH_CMD "$SERVER_USER@$SERVER_IP" "command -v docker &> /dev/null" 2>/dev/null; then
    echo "⚠️  Docker не установлен. Запускаю настройку сервера..."
    cat scripts/remote-setup.sh | $SSH_CMD "$SERVER_USER@$SERVER_IP" "bash -s"
    echo "⏳ Ожидание завершения установки Docker..."
    sleep 10
fi

# Создание директории на сервере (если не существует)
$SSH_CMD "$SERVER_USER@$SERVER_IP" "mkdir -p $PROJECT_DIR" 2>/dev/null || true

# Синхронизация файлов на сервер
echo "📤 Копирование файлов на сервер..."
# Используем tar+ssh для более надежной передачи
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
    --exclude='data' --exclude='*.db' -czf /tmp/wed-bobry-bot-deploy.tar.gz -C "$LOCAL_DIR" .

$SCP_CMD /tmp/wed-bobry-bot-deploy.tar.gz "$SERVER_USER@$SERVER_IP:/tmp/" 2>&1
rm -f /tmp/wed-bobry-bot-deploy.tar.gz

# Копирование .env файла отдельно
echo "📤 Копирование .env файла..."
$SCP_CMD "$LOCAL_DIR/.env" "$SERVER_USER@$SERVER_IP:$PROJECT_DIR/.env.new" 2>&1 || true

# Выполнение команд на сервере
echo "🔧 Настройка и запуск бота на сервере..."
$SSH_CMD "$SERVER_USER@$SERVER_IP" << 'ENDSSH'
set -e
cd /opt/wed-bobry-bot

# Распаковка файлов
if [ -f /tmp/wed-bobry-bot-deploy.tar.gz ]; then
    echo "📦 Распаковка файлов проекта..."
    tar -xzf /tmp/wed-bobry-bot-deploy.tar.gz -C /opt/wed-bobry-bot
    rm -f /tmp/wed-bobry-bot-deploy.tar.gz
fi

# Создание директории data если не существует
mkdir -p data

# Обновление .env файла (если новый файл существует)
if [ -f .env.new ]; then
    mv .env.new .env
    echo "✅ Файл .env обновлен"
fi

# Проверка наличия .env
if [ ! -f .env ]; then
    echo "❌ Ошибка: файл .env не найден!"
    echo "Создайте файл .env на основе .env.example"
    exit 1
fi

# Остановка существующих контейнеров
echo "🛑 Остановка существующих контейнеров..."
docker-compose down || true

# Сборка и запуск контейнеров
echo "🔨 Сборка образа..."
docker-compose build --no-cache

echo "🚀 Запуск бота..."
docker-compose up -d

# Ожидание запуска
sleep 5

# Показ логов
echo ""
echo "📋 Логи бота (последние 50 строк):"
docker-compose logs --tail=50

# Проверка статуса
echo ""
echo "📊 Статус контейнеров:"
docker-compose ps

ENDSSH

echo ""
echo "✅ Развертывание завершено!"
echo "Для просмотра логов выполните: ssh $SERVER_USER@$SERVER_IP 'cd $PROJECT_DIR && docker-compose logs -f'"
