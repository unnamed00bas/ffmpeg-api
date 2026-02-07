# Nginx Configuration - Production Guide

Это руководство по настройке Nginx reverse proxy с SSL сертификатами для production окружения FFmpeg API.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [SSL сертификаты](#ssl-сертификаты)
- [Let's Encrypt (Certbot)](#lets-encrypt-certbot)
- [Настройка Rate Limiting](#настройка-rate-limiting)
- [Security Headers](#security-headers)
- [Мониторинг и логирование](#мониторинг-и-логирование)
- [Troubleshooting](#troubleshooting)

## Быстрый старт

### Для тестирования с самоподписанными сертификатами

```bash
# 1. Генерация тестовых сертификатов
cd docker/nginx
chmod +x generate_test_ssl.sh
./generate_test_ssl.sh

# 2. Запуск production окружения
cd ../..
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d

# 3. Проверка
curl -k https://localhost/health
```

### Для production с Let's Encrypt

```bash
# 1. Настройка .env.production
cp .env.production.example .env.production
# Измените все пароли и секреты!

# 2. Запуск базовой инфраструктуры
docker-compose -f docker-compose.prod.yml up -d postgres redis minio api worker

# 3. Получение SSL сертификатов
docker-compose -f docker-compose.prod.yml run --rm certbot certonly --webroot \
  --webroot-path /var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com -d www.yourdomain.com

# 4. Обновление nginx конфигурации для использования Let's Encrypt
# Редактируйте docker/nginx/nginx.conf
# Замените:
#   ssl_certificate /etc/nginx/ssl/cert.pem;
#   ssl_certificate_key /etc/nginx/ssl/key.pem;
# На:
#   ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
#   ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

# 5. Запуск nginx с Let's Encrypt
docker-compose -f docker-compose.prod.yml up -d nginx certbot
```

## SSL сертификаты

### Варианты SSL сертификатов

1. **Самоподписанные сертификаты** - только для тестирования
2. **Let's Encrypt** - бесплатно, доверенные CA
3. **Платные SSL сертификаты** - Comodo, DigiCert, etc.

### Самоподписанные сертификаты (Тестирование)

Используйте предоставленный скрипт для генерации:

```bash
cd docker/nginx
chmod +x generate_test_ssl.sh
./generate_test_ssl.sh
```

**Важно:** Браузеры будут показывать предупреждение о небезопасном соединении. Это нормально для самоподписанных сертификатов.

**Добавление сертификата в доверенные:**

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ssl/cert.pem
```

**Linux (Ubuntu/Debian):**
```bash
sudo cp ssl/cert.pem /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

**Linux (CentOS/RHEL):**
```bash
sudo cp ssl/cert.pem /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```

## Let's Encrypt (Certbot)

### Получение сертификата

```bash
# Сначала запустите nginx
docker-compose -f docker-compose.prod.yml up -d

# Получите сертификат
docker-compose -f docker-compose.prod.yml run --rm certbot certonly --webroot \
  --webroot-path /var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com \
  -d www.yourdomain.com \
  -d api.yourdomain.com
```

### Настройка автоматического продления

Certbot в docker-compose настроен на автоматическое продление каждые 12 часов. Проверьте его работу:

```bash
# Проверка конфигурации
docker-compose -f docker-compose.prod.yml run --rm certbot certificates

# Ручное продление (для теста)
docker-compose -f docker-compose.prod.yml run --rm certbot renew --dry-run

# Просмотр логов продления
docker logs ffmpeg-certbot-prod
```

### Wildcard сертификаты

Для wildcard сертификатов потребуется DNS challenge вместо webroot:

```bash
docker-compose -f docker-compose.prod.yml run --rm certbot certonly --manual \
  --preferred-challenges dns \
  --email your-email@example.com \
  --agree-tos \
  -d "*.yourdomain.com" -d "yourdomain.com"
```

**Примечание:** Вам будет предложено добавить DNS TXT запись для подтверждения владения доменом.

## Настройка Rate Limiting

Nginx использует два типа rate limiting:

### 1. Request Rate Limiting

Ограничивает количество запросов в секунду:

```nginx
# В nginx.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# В location блоке
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    # ...
}
```

**Параметры:**
- `rate=10r/s` - 10 запросов в секунду
- `burst=20` - разрешает кратковременные всплески до 20 запросов
- `nodelay` - не задерживает запросы в burst, сразу отклоняет превышение

### 2. Connection Rate Limiting

Ограничивает количество одновременных соединений:

```nginx
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    limit_conn conn_limit 10;
    # ...
}
```

### Настройка для разных endpoint'ов

**API endpoints (умеренный):**
```nginx
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    limit_req_status 429;
}
```

**Auth endpoints (строгий):**
```nginx
location /api/v1/auth/ {
    limit_req zone=auth_limit burst=3 nodelay;
    limit_req_status 429;
}
```

**Health check (без ограничений):**
```nginx
location /health {
    # Без rate limiting
}
```

### Настройка значений для production

В `.env.production`:

```bash
# Приложение уровень (дополняет nginx)
RATE_LIMIT_PER_MINUTE=600
RATE_LIMIT_PER_HOUR=10000
```

В `nginx.conf`:
```nginx
# Для публичного API: 10-20 req/s
limit_req_zone $binary_remote_addr zone=public_api:10m rate=10r/s;

# Для authenticated users: 20-50 req/s
limit_req_zone $user_id zone=authenticated_api:10m rate=30r/s;

# Для auth endpoints: 5 req/min
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;
```

## Security Headers

### Обзор настроенных заголовков

```nginx
# HSTS - HTTP Strict Transport Security
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# X-Frame-Options - защита от clickjacking
add_header X-Frame-Options "SAMEORIGIN" always;

# X-Content-Type-Options - защита от MIME type sniffing
add_header X-Content-Type-Options "nosniff" always;

# X-XSS-Protection - XSS защита для старых браузеров
add_header X-XSS-Protection "1; mode=block" always;

# Referrer-Policy
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Content-Security-Policy (CSP)
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
```

### Настройка CSP для вашего фронтенда

Если у вас есть фронтенд на другом домене, добавьте его в CSP:

```nginx
add_header Content-Security-Policy "
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.yourdomain.com;
    style-src 'self' 'unsafe-inline' https://cdn.yourdomain.com;
    img-src 'self' data: https:;
    font-src 'self' https://cdn.yourdomain.com;
    connect-src 'self' https://api.yourdomain.com;
    frame-ancestors 'self';
" always;
```

### Дополнительные заголовки

**Server header:**
```nginx
server_tokens off;  # Скрывает версию nginx
```

**Powered by:**
```nginx
# Удаляет X-Powered-By заголовки (если они есть)
more_clear_headers 'X-Powered-By';
```

## Мониторинг и логирование

### Логирование

```nginx
# Access log в формате combined
access_log /var/log/nginx/access.log combined;

# Error log
error_log /var/log/nginx/error.log warn;
```

### Просмотр логов

```bash
# Все логи nginx
docker-compose -f docker-compose.prod.yml logs -f nginx

# Error log только
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/error.log

# Access log с фильтрацией по статус коду
docker-compose -f docker-compose.prod.yml exec nginx grep " 429 " /var/log/nginx/access.log
```

### Мониторинг rate limiting

Добавьте в лог формат информацию о rate limiting:

```nginx
log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                '$status $body_bytes_sent "$http_referer" '
                '"$http_user_agent" "$http_x_forwarded_for" '
                'rt=$request_time uct="$upstream_connect_time" '
                'uht="$upstream_header_time" urt="$upstream_response_time" '
                'limit_req_status=$limit_req_status';
```

### Prometheus мониторинг

Nginx экспортер для Prometheus (опционально):

```bash
# Добавить в docker-compose.prod.yml
nginx-exporter:
  image: nginx/nginx-prometheus-exporter:latest
  command:
    - -nginx.scrape-uri=http://nginx:8080/stub_status
  ports:
    - "9113:9113"
```

## Troubleshooting

### Проблема: Сертификат не обновляется

**Решение:**

```bash
# Проверьте статус сертификатов
docker-compose -f docker-compose.prod.yml run --rm certbot certificates

# Ручное продление
docker-compose -f docker-compose.prod.yml run --rm certbot renew

# Проверьте логи
docker logs ffmpeg-certbot-prod
```

### Проблема: 502 Bad Gateway

**Причины:**
- API сервис недоступен
- Неверный upstream конфигурация
- Таймауты

**Решение:**

```bash
# Проверьте статус API
docker-compose -f docker-compose.prod.yml ps api
docker-compose -f docker-compose.prod.yml logs api

# Проверьте upstream
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Увеличьте таймауты в nginx.conf
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

### Проблема: 429 Too Many Requests

**Причины:**
- Превышен rate limit
- Burst недостаточен

**Решение:**

```bash
# Настройте rate limiting в nginx.conf
# Увеличьте rate или burst
limit_req zone=api_limit burst=30 nodelay;

# Или временно отключите для тестирования
# limit_req off;
```

### Проблема: SSL handshake failed

**Решение:**

```bash
# Проверьте сертификаты
docker-compose -f docker-compose.prod.yml exec nginx ls -la /etc/nginx/ssl/

# Проверьте права доступа
docker-compose -f docker-compose.prod.yml exec nginx chmod 600 /etc/nginx/ssl/key.pem
docker-compose -f docker-compose.prod.yml exec nginx chmod 644 /etc/nginx/ssl/cert.pem

# Проверьте конфигурацию
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Перезагрузите nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### Проблема: Загрузка больших файлов не работает

**Решение:**

```bash
# Проверьте client_max_body_size в nginx.conf
client_max_body_size 1G;

# Проверьте proxy settings
proxy_request_buffering off;

# Также проверьте настройки в .env.production
MAX_UPLOAD_SIZE=1073741824
```

## Полезные команды

### Управление Nginx

```bash
# Проверка конфигурации
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Перезагрузка конфигурации (без downtime)
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# Полный рестарт
docker-compose -f docker-compose.prod.yml restart nginx

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### Тестирование SSL

```bash
# Проверка SSL сертификата
openssl s_client -connect localhost:443 -servername localhost

# Проверка TLS версии
nmap --script ssl-enum-ciphers -p 443 localhost

# Тест с curl
curl -I https://localhost
curl -v https://localhost/health
```

### Тестирование rate limiting

```bash
# Тест API rate limiting
for i in {1..25}; do curl -w "\nStatus: %{http_code}\n" https://localhost/api/v1/health; done

# Тест auth rate limiting
for i in {1..10}; do curl -X POST https://localhost/api/v1/auth/login; done
```

## Дополнительные ресурсы

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Nginx Rate Limiting](https://www.nginx.com/blog/rate-limiting-nginx/)

## Безопасность

### Проверка безопасности

```bash
# SSL Labs Test
# https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com

# Mozilla Observatory
# https://observatory.mozilla.org/analyze/yourdomain.com

# Security Headers
# https://securityheaders.com/
```

### Best Practices

1. **Всегда используйте HTTPS в production**
2. **Регулярно обновляйте сертификаты** (Let's Encrypt делает это автоматически)
3. **Настройте rate limiting** для защиты от DDoS
4. **Используйте strong SSL/TLS конфигурацию** (настроено в nginx.conf)
5. **Мониторьте логи** на предмет подозрительной активности
6. **Регулярно обновляйте Nginx**
7. **Используйте firewall** для ограничения доступа к портам
8. **Сделайте бэкап конфигураций** и сертификатов

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose -f docker-compose.prod.yml logs -f`
2. Проверьте конфигурацию: `docker-compose -f docker-compose.prod.yml exec nginx nginx -t`
3. Проверьте документацию по ссылкам выше
4. Создайте issue в репозитории проекта
