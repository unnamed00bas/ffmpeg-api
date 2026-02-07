#!/bin/bash
# Скрипт для получения SSL сертификатов Let's Encrypt
# Использование: ./init-letsencrypt.sh yourdomain.com your@email.com

set -e

DOMAIN=${1:-""}
EMAIL=${2:-""}

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Использование: $0 <domain> <email>"
    echo "Пример: $0 api.example.com admin@example.com"
    exit 1
fi

echo "=========================================="
echo "Получение SSL сертификата Let's Encrypt"
echo "Домен: $DOMAIN"
echo "Email: $EMAIL"
echo "=========================================="

# 1. Создаём необходимые директории
echo "[1/5] Создание директорий..."
mkdir -p ./docker/nginx/certbot-webroot
mkdir -p ./docker/nginx/ssl

# 2. Перезапускаем nginx без SSL
echo "[2/5] Запуск nginx (только HTTP)..."
docker-compose up -d nginx

# Ждём запуска nginx
sleep 5

# 3. Проверяем доступность
echo "[3/5] Проверка доступности домена..."
if ! curl -s --head "http://$DOMAIN/.well-known/acme-challenge/" | head -n 1 | grep -q "404\|200"; then
    echo "ОШИБКА: Домен $DOMAIN недоступен через HTTP"
    echo "Убедитесь что:"
    echo "  - DNS записи настроены правильно"
    echo "  - Порт 80 открыт в firewall"
    exit 1
fi

# 4. Получаем сертификат
echo "[4/5] Получение сертификата Let's Encrypt..."
docker run --rm \
    -v $(pwd)/docker/nginx/ssl:/etc/letsencrypt \
    -v $(pwd)/docker/nginx/certbot-webroot:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

if [ $? -ne 0 ]; then
    echo "ОШИБКА: Не удалось получить сертификат"
    exit 1
fi

# 5. Создаём SSL конфигурацию nginx
echo "[5/5] Настройка nginx с SSL..."
mkdir -p ./docker/nginx/ssl-enabled
sed "s/ffmpeg.promaren.ru/$DOMAIN/g" ./docker/nginx/conf.d/ssl.conf.template > ./docker/nginx/ssl-enabled/ssl.conf

# Перезапускаем nginx с SSL
docker-compose restart nginx

echo ""
echo "=========================================="
echo "SSL сертификат успешно установлен!"
echo "=========================================="
echo ""
echo "Сертификат: ./docker/nginx/ssl/live/$DOMAIN/"
echo ""
echo "Для автоматического обновления сертификат обновляется"
echo "контейнером certbot каждые 12 часов автоматически."
echo ""

