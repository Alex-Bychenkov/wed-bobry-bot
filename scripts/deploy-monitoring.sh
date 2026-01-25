#!/bin/bash
set -e

SERVER_IP="87.247.157.122"
SERVER_USER="root"
SERVER_PASS="${SERVER_PASS:-F65NkiCBmM}"
MONITORING_DIR="/opt/monitoring"
LOCAL_MONITORING_DIR="./monitoring"

# Определение команды SSH
if command -v sshpass &> /dev/null && [ -n "$SERVER_PASS" ]; then
    SSH_CMD="sshpass -p '$SERVER_PASS' ssh -o StrictHostKeyChecking=no -T"
    SCP_CMD="sshpass -p '$SERVER_PASS' scp -o StrictHostKeyChecking=no"
else
    SSH_CMD="ssh"
    SCP_CMD="scp"
fi

echo "🚀 Развертывание мониторинга на сервер $SERVER_IP..."

# Проверка наличия директории мониторинга
if [ ! -d "$LOCAL_MONITORING_DIR" ]; then
    echo "❌ Ошибка: директория monitoring не найдена!"
    exit 1
fi

# Проверка наличия .env файла для мониторинга (необязательно, если есть на сервере)
if [ ! -f "$LOCAL_MONITORING_DIR/.env" ]; then
    echo "⚠️  Локальный файл .env не найден. Будет использован существующий на сервере или создан новый."
    ENV_FILE_EXISTS=false
else
    ENV_FILE_EXISTS=true
fi

# Проверка настройки сервера
echo "🔍 Проверка настройки сервера..."
if ! $SSH_CMD "$SERVER_USER@$SERVER_IP" "command -v docker &> /dev/null" 2>/dev/null; then
    echo "❌ Docker не установлен на сервере!"
    echo "   Выполните сначала: ./scripts/deploy.sh"
    exit 1
fi

# Создание директории на сервере
echo "📁 Создание директории мониторинга на сервере..."
$SSH_CMD "$SERVER_USER@$SERVER_IP" "mkdir -p $MONITORING_DIR" 2>/dev/null || true

# Создание архива файлов мониторинга
echo "📦 Подготовка файлов для передачи..."
cd "$LOCAL_MONITORING_DIR"
tar --exclude='.env' --exclude='telegram-bot-data' \
    --exclude='*.db' -czf /tmp/monitoring-deploy.tar.gz .

# Копирование архива на сервер
echo "📤 Копирование файлов на сервер..."
$SCP_CMD /tmp/monitoring-deploy.tar.gz "$SERVER_USER@$SERVER_IP:/tmp/" 2>&1
rm -f /tmp/monitoring-deploy.tar.gz

# Копирование .env файла отдельно (если существует)
if [ "$ENV_FILE_EXISTS" = true ]; then
    echo "📤 Копирование .env файла..."
    $SCP_CMD "$LOCAL_MONITORING_DIR/.env" "$SERVER_USER@$SERVER_IP:$MONITORING_DIR/.env.new" 2>&1 || true
else
    echo "⚠️  Локальный .env файл не найден, будет использован существующий на сервере"
fi

# Выполнение команд на сервере
echo "🔧 Настройка и запуск мониторинга на сервере..."
$SSH_CMD "$SERVER_USER@$SERVER_IP" << 'ENDSSH'
set -e
cd /opt/monitoring

# Распаковка файлов
if [ -f /tmp/monitoring-deploy.tar.gz ]; then
    echo "📦 Распаковка файлов мониторинга..."
    tar -xzf /tmp/monitoring-deploy.tar.gz -C /opt/monitoring
    rm -f /tmp/monitoring-deploy.tar.gz
fi

# Обновление .env файла (если новый файл существует)
if [ -f .env.new ]; then
    mv .env.new .env
    echo "✅ Файл .env обновлен"
fi

# Создание .env из примера, если его нет
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📋 Создание .env из .env.example..."
        cp .env.example .env
        echo "⚠️  ВНИМАНИЕ: Не забудьте заполнить TELEGRAM_ALERT_BOT_TOKEN в файле .env!"
    else
        echo "❌ Ошибка: файл .env не найден и .env.example также отсутствует!"
        exit 1
    fi
fi

# Создание директории для данных telegram бота
mkdir -p telegram-bot-data

# Удаление служебных файлов macOS (могут вызывать ошибки в Grafana)
echo "🧹 Очистка служебных файлов macOS..."
find grafana/ -name "._*" -type f -delete 2>/dev/null || true
find . -name ".DS_Store" -type f -delete 2>/dev/null || true

# Остановка существующих контейнеров мониторинга
echo "🛑 Остановка существующих контейнеров мониторинга..."
docker-compose -f docker-compose.monitoring.yml down || true

# Запуск контейнеров мониторинга
echo "🚀 Запуск мониторинга..."
docker-compose -f docker-compose.monitoring.yml up -d

# Ожидание запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Показ логов
echo ""
echo "📋 Логи мониторинга (последние 30 строк):"
docker-compose -f docker-compose.monitoring.yml logs --tail=30

# Проверка статуса
echo ""
echo "📊 Статус контейнеров мониторинга:"
docker-compose -f docker-compose.monitoring.yml ps

# Проверка доступности сервисов
echo ""
echo "🔍 Проверка доступности сервисов..."
sleep 5

# Проверка Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus доступен на порту 9090"
else
    echo "⚠️  Prometheus не отвечает на порту 9090"
fi

# Проверка Grafana
if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana доступен на порту 3000"
else
    echo "⚠️  Grafana не отвечает на порту 3000"
fi

# Проверка Node Exporter
if curl -s http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✅ Node Exporter доступен на порту 9100"
else
    echo "⚠️  Node Exporter не отвечает на порту 9100"
fi

# Проверка Alertmanager
if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
    echo "✅ Alertmanager доступен на порту 9093"
else
    echo "⚠️  Alertmanager не отвечает на порту 9093"
fi

ENDSSH

echo ""
echo "✅ Развертывание мониторинга завершено!"
echo ""
echo "📊 Доступ к сервисам:"
echo "   - Prometheus: http://$SERVER_IP:9090"
echo "   - Grafana: http://$SERVER_IP:3000 (admin/admin)"
echo "   - Alertmanager: http://$SERVER_IP:9093"
echo ""
echo "Для просмотра логов выполните:"
echo "  ssh $SERVER_USER@$SERVER_IP 'cd $MONITORING_DIR && docker-compose -f docker-compose.monitoring.yml logs -f'"
