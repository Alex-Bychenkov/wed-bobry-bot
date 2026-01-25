#!/bin/bash
set -e

SERVER_IP="77.110.105.104"
SERVER_USER="root"
SERVER_PASS="${SERVER_PASS:-nH1L7n1JGAa1}"

echo "🔐 Настройка SSH-доступа к серверу $SERVER_IP..."

# Проверка наличия SSH-ключа
if [ ! -f ~/.ssh/id_ed25519.pub ] && [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "📝 Создание SSH-ключа..."
    ssh-keygen -t ed25519 -C "wed-bobry-bot" -f ~/.ssh/id_ed25519 -N ""
    echo "✅ SSH-ключ создан"
fi

# Определение публичного ключа
if [ -f ~/.ssh/id_ed25519.pub ]; then
    PUB_KEY_FILE=~/.ssh/id_ed25519.pub
elif [ -f ~/.ssh/id_rsa.pub ]; then
    PUB_KEY_FILE=~/.ssh/id_rsa.pub
else
    echo "❌ Ошибка: публичный SSH-ключ не найден"
    exit 1
fi

echo "🔑 Публичный ключ:"
cat "$PUB_KEY_FILE"
echo ""

# Проверка, работает ли уже SSH-ключ
echo "🔍 Проверка существующего SSH-доступа..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "echo 'SSH key работает'" 2>/dev/null; then
    echo "✅ SSH-ключ уже настроен! Подключение работает без пароля."
    exit 0
fi

echo "📤 Копирование SSH-ключа на сервер..."

# Использование sshpass если доступен
if command -v sshpass &> /dev/null; then
    echo "Используется sshpass для копирования ключа..."
    sshpass -p "$SERVER_PASS" ssh-copy-id -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" 2>&1 || {
        echo "⚠️  ssh-copy-id не сработал, пробую альтернативный метод..."
        
        # Альтернативный метод: копирование ключа вручную
        PUB_KEY=$(cat "$PUB_KEY_FILE")
        sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$PUB_KEY' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys" 2>&1
        
        if [ $? -eq 0 ]; then
            echo "✅ SSH-ключ успешно скопирован альтернативным методом"
        else
            echo "❌ Не удалось скопировать SSH-ключ"
            exit 1
        fi
    }
else
    echo "📝 sshpass не найден. Выполните вручную:"
    echo "   ssh-copy-id $SERVER_USER@$SERVER_IP"
    echo ""
    echo "Или скопируйте ключ вручную:"
    echo "   cat $PUB_KEY_FILE | ssh $SERVER_USER@$SERVER_IP 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'"
    exit 1
fi

# Проверка подключения
echo ""
echo "🔍 Проверка подключения..."
sleep 2

if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "echo 'SSH key работает'" 2>/dev/null; then
    echo "✅ SSH-ключ успешно настроен! Теперь можно подключаться без пароля."
    echo ""
    echo "Проверка:"
    ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "echo '✅ Подключение работает!' && uname -a"
else
    echo "⚠️  SSH-ключ скопирован, но автоматическая проверка не прошла."
    echo "Попробуйте подключиться вручную:"
    echo "   ssh $SERVER_USER@$SERVER_IP"
fi
