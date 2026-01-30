# Оптимизация использования памяти Prometheus

## Важно понимать

**Удаление панелей из Grafana НЕ уменьшит использование памяти Prometheus!**

Prometheus собирает и хранит ВСЕ метрики независимо от того, используются ли они в Grafana dashboards. Чтобы уменьшить память, нужно настроить Prometheus так, чтобы он **не собирал** ненужные метрики.

## Внесенные изменения

### 1. Фильтрация метрик Node Exporter (`prometheus.yml`)

Добавлен `metric_relabel_configs` для отсеивания неиспользуемых метрик Node Exporter. Теперь Prometheus собирает только те метрики, которые используются в dashboards:

**Оставляем:**
- `node_cpu_seconds_total` - для CPU метрик
- `node_memory_*` - для Memory метрик  
- `node_filesystem_*` - для Disk метрик
- `node_time_seconds`, `node_boot_time_seconds` - для Uptime
- `node_network_*` - для Network метрик

**Отсеиваем:**
- Все остальные метрики Node Exporter (их сотни, но они не используются)

### 2. Фильтрация метрик Prometheus self-monitoring

Отсеиваем детальные метрики Prometheus, которые не используются:
- `prometheus_tsdb_*` - детальные метрики TSDB
- `prometheus_http_request_duration_seconds_bucket` - детальные метрики HTTP запросов
- И другие неиспользуемые метрики

### 2.1. Фильтрация метрик бота

Удалены неиспользуемые панели из Grafana и настроена фильтрация в Prometheus для отсеивания соответствующих метрик:

**Удаленные панели:**
- Response Time by Handler
- Commands by Type
- Player Responses Over Time
- Team Selections (Total)
- Team Changes Over Time
- Guests Added
- Guests Deleted
- Total Team Changes
- Total Team Selections

**Отсеиваемые метрики:**
- `bot_team_changes_total` - метрики смены команд
- `bot_guests_added_total` - метрики добавления гостей
- `bot_guests_deleted_total` - метрики удаления гостей
- `bot_responses_total` - метрики ответов игроков

### 3. Удаление неиспользуемых панелей из Grafana

Удалены 9 панелей из dashboard `bot.json`, которые не используются. Это упрощает интерфейс и снижает нагрузку на Grafana при рендеринге.

### 4. Увеличение scrape интервалов

- Prometheus self-monitoring: 60s → 120s (2 минуты)
- Node Exporter: 60s → 90s (1.5 минуты)
- Bot metrics: 30s → 45s

Это уменьшит частоту сбора метрик и нагрузку на систему.

### 5. Уменьшение retention периода

- Retention time: 7 дней → 3 дня
- Retention size: 200MB → 150MB

Меньше данных = меньше памяти.

## Ожидаемый эффект

1. **Снижение памяти Prometheus** на 40-60% за счет отсеивания неиспользуемых метрик Node Exporter
2. **Дополнительная экономия памяти** за счет отсеивания 4 неиспользуемых метрик бота (~10-15% дополнительно)
3. **Снижение нагрузки на систему** за счет увеличенных scrape интервалов
4. **Меньше места на диске** за счет уменьшенного retention
5. **Упрощение интерфейса Grafana** за счет удаления 9 неиспользуемых панелей

## Применение изменений

После применения изменений нужно перезапустить Prometheus:

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml restart prometheus
```

Или пересоздать контейнер:

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d prometheus
```

## Мониторинг эффекта

После применения изменений проверьте:

1. **Использование памяти Prometheus:**
   ```bash
   docker stats prometheus
   ```

2. **Размер данных Prometheus:**
   - Зайдите в Prometheus UI: http://your-server:9090
   - Status → TSDB Status
   - Проверьте размер базы данных

3. **Количество метрик:**
   - Prometheus UI → Status → Targets
   - Проверьте количество собранных метрик для каждого job

## Дополнительные рекомендации

Если памяти все еще не хватает:

1. **Еще больше уменьшить retention:**
   - Изменить `--storage.tsdb.retention.time=1d` (1 день)

2. **Отключить Prometheus self-monitoring:**
   - Удалить job `prometheus` из `prometheus.yml`

3. **Увеличить scrape интервалы еще больше:**
   - Node Exporter: 90s → 120s
   - Bot metrics: 45s → 60s

4. **Ограничить метрики бота:**
   - Уже выполнено: отсеиваются `bot_team_changes_total`, `bot_guests_added_total`, `bot_guests_deleted_total`, `bot_responses_total`

## Важно

- Все изменения обратно совместимы - dashboards продолжат работать
- Метрики, которые используются в dashboards, остаются без изменений
- Изменения влияют только на сбор и хранение метрик, не на их использование
