#!/bin/bash

################################################################################
# Скрипт для генерации самоподписанных SSL сертификатов для тестирования
# ВНИМАНИЕ: Используйте только для разработки и тестирования!
# Для production используйте Let's Encrypt или другой доверенный CA
################################################################################

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Директория для сертификатов
SSL_DIR="$(dirname "$0")/ssl"
CERT_FILE="$SSL_DIR/cert.pem"
KEY_FILE="$SSL_DIR/key.pem"
CSR_FILE="$SSL_DIR/cert.csr"

# Настройки сертификата
DOMAIN="localhost"
COUNTRY="RU"
STATE="Moscow"
LOCALITY="Moscow"
ORGANIZATION="FFmpeg API Development"
ORGANIZATIONAL_UNIT="IT Department"
VALIDITY_DAYS=365

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Генерация самоподписанного SSL сертификата${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Проверяем наличие openssl
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}Ошибка: OpenSSL не установлен${NC}"
    echo "Установите OpenSSL:"
    echo "  Ubuntu/Debian: sudo apt-get install openssl"
    echo "  CentOS/RHEL: sudo yum install openssl"
    echo "  macOS: brew install openssl"
    exit 1
fi

# Создаем директорию если не существует
if [ ! -d "$SSL_DIR" ]; then
    echo -e "${YELLOW}Создание директории: $SSL_DIR${NC}"
    mkdir -p "$SSL_DIR"
fi

# Проверяем, существуют ли уже сертификаты
if [ -f "$CERT_FILE" ] || [ -f "$KEY_FILE" ]; then
    echo -e "${YELLOW}ВНИМАНИЕ: SSL сертификаты уже существуют!${NC}"
    read -p "Перезаписать существующие сертификаты? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Отмена операции${NC}"
        exit 0
    fi
    echo -e "${YELLOW}Удаление старых сертификатов...${NC}"
    rm -f "$CERT_FILE" "$KEY_FILE" "$CSR_FILE"
fi

echo ""
echo -e "${GREEN}Настройки сертификата:${NC}"
echo "  Домен: $DOMAIN"
echo "  Организация: $ORGANIZATION"
echo "  Срок действия: $VALIDITY_DAYS дней"
echo ""

# Генерируем приватный ключ
echo -e "${YELLOW}Генерация приватного ключа (2048 бит)...${NC}"
openssl genrsa -out "$KEY_FILE" 2048
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Приватный ключ создан: $KEY_FILE${NC}"
else
    echo -e "${RED}✗ Ошибка генерации приватного ключа${NC}"
    exit 1
fi

# Устанавливаем права доступа к ключу
chmod 600 "$KEY_FILE"
echo -e "${GREEN}✓ Права доступа к ключу установлены: 600${NC}"

# Создаем конфигурацию для CSR
cat > "$SSL_DIR/openssl.cnf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORGANIZATION
OU = $ORGANIZATIONAL_UNIT
CN = $DOMAIN

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = *.localhost
DNS.3 = 127.0.0.1
DNS.4 = ::1
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Генерируем самоподписанный сертификат
echo ""
echo -e "${YELLOW}Генерация самоподписанного сертификата...${NC}"
openssl req -new -x509 -key "$KEY_FILE" -out "$CERT_FILE" -days $VALIDITY_DAYS \
    -config "$SSL_DIR/openssl.cnf" -extensions v3_req -sha256

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Сертификат создан: $CERT_FILE${NC}"
else
    echo -e "${RED}✗ Ошибка генерации сертификата${NC}"
    exit 1
fi

# Устанавливаем права доступа к сертификату
chmod 644 "$CERT_FILE"
echo -e "${GREEN}✓ Права доступа к сертификату установлены: 644${NC}"

# Удаляем временный конфиг
rm -f "$SSL_DIR/openssl.cnf"

# Вывод информации о сертификате
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Информация о созданном сертификате:${NC}"
echo -e "${GREEN}========================================${NC}"
openssl x509 -in "$CERT_FILE" -noout -subject -issuer -dates

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Сертификаты успешно созданы!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Файлы:"
echo "  Сертификат: $CERT_FILE"
echo "  Приватный ключ: $KEY_FILE"
echo ""
echo -e "${YELLOW}ВНИМАНИЕ:${NC}"
echo "  • Эти сертификаты ТОЛЬКО для тестирования!"
echo "  • Браузеры будут предупреждать о небезопасном соединении"
echo "  • Для production используйте Let's Encrypt (certbot)"
echo ""
echo -e "${GREEN}Для использования в Docker Compose:${NC}"
echo "  docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo -e "${YELLOW}Для добавления сертификата в доверенные (macOS):${NC}"
echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_FILE"
echo ""
echo -e "${YELLOW}Для добавления сертификата в доверенные (Linux):${NC}"
echo "  sudo cp $CERT_FILE /usr/local/share/ca-certificates/"
echo "  sudo update-ca-certificates"
echo ""
