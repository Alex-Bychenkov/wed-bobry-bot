# Настройка доступа к Grafana из корпоративной сети

## Проблема

Не удается подключиться к Grafana (http://87.247.157.122:3000) из корпоративной сети X5.

## Возможные причины

### 1. Firewall на сервере блокирует порт 3000

**Решение: Открыть порт 3000 в UFW**

```bash
# Подключитесь к серверу
ssh root@87.247.157.122

# Проверьте статус firewall
ufw status

# Откройте порт 3000 для всех
ufw allow 3000/tcp

# Или только для определенного IP/подсети (рекомендуется)
ufw allow from 10.0.0.0/8 to any port 3000 proto tcp
ufw allow from 172.16.0.0/12 to any port 3000 proto tcp
ufw allow from 192.168.0.0/16 to any port 3000 proto tcp

# Проверьте статус
ufw status numbered
```

### 2. Docker не прослушивает на всех интерфейсах

Текущая конфигурация в `docker-compose.monitoring.yml`:
```yaml
ports:
  - "3000:3000"
```

Это привязывает порт ко всем интерфейсам (`0.0.0.0:3000`), что правильно.

**Проверка:**
```bash
# На сервере проверьте, на каком интерфейсе слушает порт
netstat -tlnp | grep 3000

# Или
ss -tlnp | grep 3000

# Должно быть: 0.0.0.0:3000 или :::3000
```

### 3. Корпоративный firewall/прокси X5 блокирует порт 3000

Многие корпоративные сети блокируют нестандартные порты (разрешены только 80, 443, 22 и т.д.).

**Решение A: Использовать стандартный HTTPS порт (443) с nginx**

Установите nginx как reverse proxy:

```bash
# На сервере
apt update
apt install nginx certbot python3-certbot-nginx -y

# Создайте конфигурацию nginx
cat > /etc/nginx/sites-available/grafana << 'EOF'
server {
    listen 80;
    server_name grafana.yourdomain.com;  # Замените на ваш домен

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Активируйте конфигурацию
ln -s /etc/nginx/sites-available/grafana /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Установите SSL сертификат (опционально, но рекомендуется)
certbot --nginx -d grafana.yourdomain.com
```

Теперь Grafana будет доступна по:
- HTTP: http://grafana.yourdomain.com (порт 80)
- HTTPS: https://grafana.yourdomain.com (порт 443)

**Решение B: Использовать SSH туннель**

Если у вас есть SSH доступ к серверу из корпоративной сети:

```bash
# На вашем компьютере в корпоративной сети
ssh -L 3000:localhost:3000 root@87.247.157.122

# Теперь открывайте в браузере
http://localhost:3000
```

**Решение C: Использовать VPN**

Настройте VPN (WireGuard/OpenVPN) на сервере и подключайтесь к серверу через VPN.

### 4. Grafana настроена неправильно

Проверьте переменную `GF_SERVER_ROOT_URL` в docker-compose:

```yaml
environment:
  - GF_SERVER_ROOT_URL=http://87.247.157.122:3000
```

Если используете домен или nginx, измените на:
```yaml
environment:
  - GF_SERVER_ROOT_URL=https://grafana.yourdomain.com
```

### 5. Проблема с DNS или маршрутизацией

**Проверка доступности сервера:**

```bash
# С вашего компьютера в корпоративной сети
ping 87.247.157.122

# Проверка доступности порта
telnet 87.247.157.122 3000

# Или с помощью nc (netcat)
nc -zv 87.247.157.122 3000

# Или через curl
curl -v http://87.247.157.122:3000
```

## Рекомендованное решение для корпоративной сети

### Вариант 1: Nginx Reverse Proxy с HTTPS (РЕКОМЕНДУЕТСЯ)

**Преимущества:**
- ✅ Работает через стандартные порты 80/443
- ✅ Поддержка HTTPS/SSL
- ✅ Не блокируется корпоративными firewall
- ✅ Можно настроить базовую аутентификацию

**Шаги:**

1. **Получите домен или поддомен** (например, `grafana.yourdomain.com`)

2. **Настройте DNS** - добавьте A-запись, указывающую на IP сервера:
   ```
   grafana.yourdomain.com -> 87.247.157.122
   ```

3. **Установите nginx на сервер:**
   ```bash
   ssh root@87.247.157.122
   apt update
   apt install nginx certbot python3-certbot-nginx -y
   ```

4. **Создайте конфигурацию nginx:**
   ```bash
   cat > /etc/nginx/sites-available/grafana << 'EOF'
   server {
       listen 80;
       server_name grafana.yourdomain.com;

       # Redirect HTTP to HTTPS
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name grafana.yourdomain.com;

       # SSL certificates (will be added by certbot)
       
       # Security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Frame-Options "SAMEORIGIN" always;
       add_header X-Content-Type-Options "nosniff" always;

       # Proxy to Grafana
       location / {
           proxy_pass http://localhost:3000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   EOF

   # Активируйте конфигурацию
   ln -sf /etc/nginx/sites-available/grafana /etc/nginx/sites-enabled/
   nginx -t
   systemctl restart nginx
   ```

5. **Получите SSL сертификат (Let's Encrypt):**
   ```bash
   certbot --nginx -d grafana.yourdomain.com
   ```

6. **Обновите Grafana конфигурацию:**
   
   Отредактируйте `/opt/monitoring/docker-compose.monitoring.yml`:
   ```yaml
   grafana:
     environment:
       - GF_SERVER_ROOT_URL=https://grafana.yourdomain.com
       - GF_SERVER_DOMAIN=grafana.yourdomain.com
   ```

   Перезапустите Grafana:
   ```bash
   cd /opt/monitoring
   docker-compose -f docker-compose.monitoring.yml restart grafana
   ```

7. **Откройте порты в firewall:**
   ```bash
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw status
   ```

8. **Готово!** Теперь доступ по:
   ```
   https://grafana.yourdomain.com
   ```

### Вариант 2: SSH Туннель (Быстрое решение)

Если у вас есть SSH доступ:

```bash
# На вашем компьютере
ssh -N -L 3000:localhost:3000 root@87.247.157.122
```

Оставьте терминал открытым и откройте в браузере:
```
http://localhost:3000
```

### Вариант 3: Открыть порт 3000 в firewall

Если корпоративная сеть X5 не блокирует порт 3000:

```bash
# На сервере
ssh root@87.247.157.122

# Откройте порт для корпоративной сети X5
# Узнайте IP-адрес или подсеть вашей корпоративной сети
ufw allow from YOUR_CORP_IP/MASK to any port 3000 proto tcp

# Или для всех (менее безопасно)
ufw allow 3000/tcp

# Проверьте
ufw status numbered
```

## Диагностика

### На сервере:

```bash
# Проверьте, запущена ли Grafana
docker ps | grep grafana

# Проверьте логи Grafana
cd /opt/monitoring
docker-compose -f docker-compose.monitoring.yml logs grafana

# Проверьте, на каком интерфейсе слушает порт
ss -tlnp | grep 3000

# Проверьте firewall
ufw status numbered

# Проверьте, доступна ли Grafana локально
curl -v http://localhost:3000/api/health
```

### С вашего компьютера в корпоративной сети:

```bash
# Проверьте доступность сервера
ping 87.247.157.122

# Проверьте доступность порта 3000
telnet 87.247.157.122 3000

# Или через curl
curl -v http://87.247.157.122:3000

# Проверьте через HTTP
curl -I http://87.247.157.122:3000
```

## Быстрый чеклист

- [ ] Grafana запущена: `docker ps | grep grafana`
- [ ] Порт 3000 слушает на 0.0.0.0: `ss -tlnp | grep 3000`
- [ ] Firewall разрешает порт 3000: `ufw status | grep 3000`
- [ ] Сервер доступен из корпоративной сети: `ping 87.247.157.122`
- [ ] Порт 3000 доступен: `telnet 87.247.157.122 3000`
- [ ] Grafana отвечает: `curl http://87.247.157.122:3000/api/health`

## Следующие шаги

1. **Проверьте firewall на сервере** - скорее всего, порт 3000 закрыт
2. **Если не помогает** - настройте nginx reverse proxy с доменом
3. **Временное решение** - используйте SSH туннель

## Контакты для помощи

Если проблема не решается:
1. Проверьте логи Grafana: `docker-compose logs grafana`
2. Свяжитесь с сетевым администратором X5 для проверки блокировки портов
3. Рассмотрите использование VPN для доступа к серверу
