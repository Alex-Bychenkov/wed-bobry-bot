#!/bin/bash

SERVER_IP="87.247.157.122"
SERVER_USER="root"
SERVER_PASS="${SERVER_PASS:-F65NkiCBmM}"

echo "🔍 Проверка статуса бота на сервере $SERVER_IP..."
echo ""

# Проверка подключения
echo "1️⃣ Проверка подключения к серверу..."
if ping -c 2 "$SERVER_IP" > /dev/null 2>&1; then
    echo "✅ Сервер доступен"
else
    echo "❌ Сервер недоступен"
    exit 1
fi

echo ""
echo "2️⃣ Проверка Docker контейнеров..."
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -T "$SERVER_USER@$SERVER_IP" << 'EOF'
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
EOF

echo ""
echo "3️⃣ Последние логи бота (последние 30 строк)..."
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -T "$SERVER_USER@$SERVER_IP" << 'EOF'
docker logs --tail=30 wed-bobry-bot 2>&1
EOF

echo ""
echo "4️⃣ Проверка на конфликты..."
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -T "$SERVER_USER@$SERVER_IP" << 'EOF'
if docker logs --tail=50 wed-bobry-bot 2>&1 | grep -q "Conflict.*getUpdates"; then
    echo "⚠️  ОБНАРУЖЕН КОНФЛИКТ: Запущено несколько экземпляров бота!"
    echo "   Это может быть локальная копия или другой сервер."
else
    echo "✅ Конфликтов не обнаружено - бот работает нормально"
fi
EOF

echo ""
echo "✅ Проверка завершена!"
