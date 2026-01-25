# Инструкция по использованию мониторинга

## Быстрый доступ

### Веб-интерфейсы

- **Prometheus**: http://87.247.157.122:9090
  - Просмотр метрик, запросы PromQL, статус targets
- **Grafana**: http://87.247.157.122:3000
  - Логин: `admin` / Пароль: `admin`
  - Дашборды для визуализации метрик
- **Alertmanager**: http://87.247.157.122:9093
  - Просмотр активных алертов, управление уведомлениями

### Проблемы с доступом из корпоративной сети?

Если вы не можете подключиться к Grafana/Prometheus из корпоративной сети:

**🚀 Быстрое решение - SSH туннель:**
```bash
# Для Grafana
./scripts/grafana-tunnel.sh

# Или вручную
ssh -L 3000:localhost:3000 root@87.247.157.122
```
Затем откройте: http://localhost:3000

**🔍 Диагностика проблемы:**
```bash
./scripts/check-grafana-access.sh
```

📖 **Подробные инструкции по настройке доступа:** [../GRAFANA_ACCESS.md](../GRAFANA_ACCESS.md)

### Метрики

- **Node Exporter**: http://87.247.157.122:9100/metrics
  - Метрики сервера (CPU, память, диск, сеть)

## Управление мониторингом

### Просмотр статуса

```bash
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml ps"
```

### Просмотр логов

```bash
# Все сервисы
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs -f"

# Конкретный сервис
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs -f prometheus"
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs -f grafana"
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs -f telegram-alert-bot"
```

### Перезапуск сервисов

```bash
# Все сервисы
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml restart"

# Конкретный сервис
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml restart prometheus"
```

### Остановка/Запуск

```bash
# Остановка
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml stop"

# Запуск
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml start"

# Полная остановка с удалением контейнеров
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml down"
```

## Telegram уведомления

### Настройка

Алерты отправляются в Telegram бот **@Bych_Server_Bot**.

**ВАЖНО:** Перед использованием необходимо активировать бота:

1. Найдите бота **@Bych_Server_Bot** в Telegram
2. Отправьте команду `/start`
3. Бот сохранит ваш chat ID и начнет отправлять уведомления об алертах

### Отправка тестового алерта

Для проверки работы системы можно отправить тестовый алерт:

```bash
# Использование скрипта (с локальной машины)
cd monitoring
./send-test-alert.sh

# Или с кастомными параметрами
./send-test-alert.sh "HighCpuUsage" "warning" "Высокая загрузка CPU" "Загрузка CPU превысила 80%"

# Вручную через SSH
ssh root@87.247.157.122 "curl -X POST http://localhost:9093/api/v1/alerts -H 'Content-Type: application/json' -d '[{\"labels\":{\"alertname\":\"TestAlert\",\"severity\":\"warning\"},\"annotations\":{\"summary\":\"Тестовый алерт\",\"description\":\"Проверка работы системы\"}}]'"
```

### Как выглядят уведомления

**Активный алерт (пример):**
```
🚨 [CRITICAL] ServerDown

📋 Server is down

📝 Node exporter is not responding for more than 1 minute.

🏷️ Labels:
  • alertname: ServerDown
  • severity: critical
  • instance: 87.247.157.122:9100
  • job: node

⏰ Started: 2026-01-24 21:45:00 UTC
```

**Решенный алерт (resolved):**
```
✅ [RESOLVED] ServerDown

📋 Server is down

📝 Проблема решена. Сервер снова доступен.

🏷️ Labels:
  • alertname: ServerDown
  • severity: critical
  • instance: 87.247.157.122:9100
  • job: node

⏰ Resolved: 2026-01-24 21:46:00 UTC
```

**Формат уведомлений:**
- 🚨 для критических алертов (critical)
- ⚠️ для предупреждений (warning)
- ✅ для решенных проблем (resolved)
- Содержит название алерта, описание, метки и время

### Настроенные алерты

**Сервер:**
- `ServerDown` — сервер недоступен (критический)
- `HighCpuUsage` — загрузка CPU > 80% (предупреждение)
- `HighMemoryUsage` — использование памяти > 90% (предупреждение)
- `DiskSpaceLow` — свободного места < 15% (предупреждение)

**Бот:**
- `BotDown` — бот не отвечает (критический)
- `BotHighErrorRate` — высокая частота ошибок (предупреждение)
- `BotSlowResponses` — медленные ответы > 2 сек (предупреждение)

## Обновление мониторинга

### Деплой изменений

```bash
# С локальной машины
cd /path/to/wed_bobry_bot
./scripts/deploy-monitoring.sh
```

### Обновление конфигурации

После изменения файлов конфигурации (`prometheus.yml`, `alerts.yml`, `alertmanager.yml`):

```bash
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml restart prometheus alertmanager"
```

## Проверка работы

### Проверка доступности сервисов

```bash
# Prometheus
curl http://87.247.157.122:9090/-/healthy

# Grafana
curl http://87.247.157.122:3000/api/health

# Alertmanager
curl http://87.247.157.122:9093/-/healthy

# Node Exporter
curl http://87.247.157.122:9100/metrics | head -5
```

### Проверка targets в Prometheus

Откройте в браузере: http://87.247.157.122:9090/targets

Должны быть активны:
- `prometheus` (self-monitoring)
- `node` (node-exporter)
- `bot` (метрики бота)

### Проверка правил алертов

Откройте в браузере: http://87.247.157.122:9090/alerts

Должны быть видны все настроенные правила.

## Структура файлов

```
/opt/monitoring/
├── docker-compose.monitoring.yml  # Конфигурация Docker Compose
├── prometheus.yml                 # Конфигурация Prometheus
├── alerts.yml                     # Правила алертов
├── alertmanager.yml               # Конфигурация Alertmanager
├── .env                           # Переменные окружения (токены)
└── grafana/
    ├── provisioning/
    │   ├── datasources/           # Источники данных
    │   └── dashboards/            # Конфигурация дашбордов
    └── dashboards/                # JSON файлы дашбордов
```

## Устранение неполадок

### Grafana не запускается

```bash
# Проверьте логи
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs grafana"

# Перезапустите
ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml restart grafana"
```

### Telegram бот не отправляет уведомления

1. Проверьте, что бот запущен:
   ```bash
   ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml ps telegram-alert-bot"
   ```

2. Проверьте логи:
   ```bash
   ssh root@87.247.157.122 "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs telegram-alert-bot"
   ```

3. Убедитесь, что вы отправили `/start` боту @Bych_Server_Bot в Telegram

4. Проверьте конфигурацию `.env`:
   ```bash
   ssh root@87.247.157.122 "cat /opt/monitoring/.env"
   ```

### Prometheus не собирает метрики бота

Проверьте, что бот запущен и доступен на порту 8000:
```bash
ssh root@87.247.157.122 "curl http://localhost:8000/metrics"
```

## Полезные ссылки

- [Prometheus документация](https://prometheus.io/docs/)
- [Grafana документация](https://grafana.com/docs/)
- [Alertmanager документация](https://prometheus.io/docs/alerting/latest/alertmanager/)
