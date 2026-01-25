# Инструкция по развертыванию бота Бобры на сервере

## Подготовка

### 1. Настройка SSH-доступа

Для безопасного подключения к серверу рекомендуется настроить SSH-ключ:

```bash
# Генерация SSH-ключа (если еще не создан)
ssh-keygen -t ed25519 -C "wed-bobry-bot"

# Копирование ключа на сервер
ssh-copy-id root@87.247.157.122
```

При запросе введите пароль сервера: `F65NkiCBmM`

### 2. Проверка подключения

```bash
ssh root@87.247.157.122
```

Если подключение успешно, вы можете выйти из сессии (`exit`).

## Развертывание

### Вариант 1: Автоматическое развертывание (рекомендуется)

1. **Подготовьте файл `.env`** на локальной машине:
   ```bash
   cp .env.example .env
   # Отредактируйте .env и заполните необходимые значения
   ```

2. **Запустите скрипт развертывания**:
   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh
   ```

   Скрипт автоматически:
   - Скопирует файлы на сервер
   - Настроит сервер (если еще не настроен)
   - Запустит бота в Docker

### Вариант 2: Ручное развертывание

#### Шаг 1: Настройка сервера

Выполните на сервере скрипт настройки:

```bash
# Скопируйте скрипт на сервер
scp scripts/remote-setup.sh root@87.247.157.122:/tmp/

# Подключитесь к серверу и выполните скрипт
ssh root@87.247.157.122
chmod +x /tmp/remote-setup.sh
/tmp/remote-setup.sh
```

#### Шаг 2: Копирование файлов проекта

```bash
# Создайте архив проекта (исключая ненужные файлы)
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.env' -czf project.tar.gz .

# Скопируйте архив на сервер
scp project.tar.gz root@87.247.157.122:/opt/wed-bobry-bot/

# Распакуйте на сервере
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && tar -xzf project.tar.gz && rm project.tar.gz"
```

#### Шаг 3: Настройка переменных окружения

```bash
# Скопируйте .env.example в .env на сервере
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && cp .env.example .env"

# Отредактируйте .env файл
ssh root@87.247.157.122 "nano /opt/wed-bobry-bot/.env"
```

Заполните следующие переменные:
- `BOT_TOKEN` - токен вашего Telegram бота
- `CHAT_ID` - ID чата, где работает бот
- `ADMIN_IDS` - ID администраторов (через запятую)
- `TIMEZONE` - часовой пояс (по умолчанию Europe/Moscow)
- `NOTIFY_TIME` - время уведомлений (по умолчанию 10:00)

#### Шаг 4: Запуск бота

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose up -d"
```

## Управление ботом

### Просмотр логов

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose logs -f"
```

### Остановка бота

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose down"
```

### Перезапуск бота

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose restart"
```

### Обновление бота

```bash
# На локальной машине
./scripts/deploy.sh

# Или вручную на сервере
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && git pull && docker-compose build --no-cache && docker-compose up -d"
```

## Автозапуск

Бот автоматически запускается при перезагрузке сервера благодаря настройке `restart: unless-stopped` в `docker-compose.yml`.

Для проверки:

```bash
ssh root@87.247.157.122 "systemctl status docker"
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose ps"
```

## Мониторинг

### Проверка статуса контейнера

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose ps"
```

### Использование ресурсов

```bash
ssh root@87.247.157.122 "docker stats"
```

### Проверка логов за последний час

```bash
ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose logs --since 1h"
```

## Безопасность

### Рекомендации:

1. **Отключите вход по паролю** после настройки SSH-ключа:
   ```bash
   ssh root@87.247.157.122
   nano /etc/ssh/sshd_config
   # Установите: PasswordAuthentication no
   systemctl restart sshd
   ```

2. **Настройте fail2ban** для защиты от брутфорса (уже установлен скриптом)

3. **Регулярно обновляйте систему**:
   ```bash
   ssh root@87.247.157.122 "apt-get update && apt-get upgrade -y"
   ```

4. **Используйте не-root пользователя** для работы с ботом (опционально)

## Устранение неполадок

### Бот не запускается

1. Проверьте логи:
   ```bash
   ssh root@87.247.157.122 "cd /opt/wed-bobry-bot && docker-compose logs"
   ```

2. Проверьте файл `.env`:
   ```bash
   ssh root@87.247.157.122 "cat /opt/wed-bobry-bot/.env"
   ```

3. Проверьте статус Docker:
   ```bash
   ssh root@87.247.157.122 "systemctl status docker"
   ```

### Проблемы с подключением к серверу

1. Проверьте доступность сервера:
   ```bash
   ping 87.247.157.122
   ```

2. Проверьте SSH-ключ:
   ```bash
   ssh -v root@87.247.157.122
   ```

## Контакты и поддержка

При возникновении проблем проверьте:
- Логи бота: `docker-compose logs`
- Статус контейнеров: `docker-compose ps`
- Статус Docker: `systemctl status docker`
