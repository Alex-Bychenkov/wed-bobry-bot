#!/bin/bash
set -e

echo "🚀 Настройка сервера для развертывания бота Бобры..."

# Обновление системы
echo "📦 Обновление системы..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get upgrade -y
    apt-get install -y curl git wget ufw fail2ban
elif command -v yum &> /dev/null; then
    yum update -y
    yum install -y curl git wget firewalld fail2ban
elif command -v apk &> /dev/null; then
    apk update
    apk add --no-cache curl git wget ufw fail2ban
fi

# Установка Docker
echo "🐳 Установка Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
else
    echo "Docker уже установлен"
fi

# Установка Docker Compose
echo "🐳 Установка Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
else
    echo "Docker Compose уже установлен"
fi

# Настройка файрвола
echo "🔥 Настройка файрвола..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw reload
elif command -v firewall-cmd &> /dev/null; then
    systemctl enable firewalld
    systemctl start firewalld
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
fi

# Создание директории для проекта
echo "📁 Создание директории для проекта..."
mkdir -p /opt/wed-bobry-bot
mkdir -p /opt/wed-bobry-bot/data

# Настройка прав
chown -R root:root /opt/wed-bobry-bot

echo "✅ Сервер настроен успешно!"
echo ""
echo "Следующие шаги:"
echo "1. Скопируйте файлы проекта в /opt/wed-bobry-bot"
echo "2. Создайте файл .env с настройками бота"
echo "3. Запустите бота с помощью docker-compose"
