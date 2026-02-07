# Deployment Guide

## Локальное развертывание

### Требования

- Docker 20.10+
- Docker Compose 2.0+
- Не менее 8GB RAM
- Не менее 20GB свободного места на диске

### Быстрый старт

1. Клонирование репозитория
```bash
git clone <repository-url>
cd ffmpeg-api
```

2. Настройка переменных окружения
```bash
cp .env.example .env
# Отредактировать .env с нужными значениями
```

3. Запуск сервисов
```bash
docker-compose up -d
```

4. Создание базы данных
```bash
docker-compose exec api python scripts/init_db.py
```

5. Создание admin пользователя
```bash
docker-compose exec api python scripts/create_admin.py
```

6. Проверка работоспособности
```bash
curl http://localhost:8000/api/v1/health
```

### Docker Compose сервисы

```yaml
version: '3.8'

services:
  # Nginx - API Gateway и Load Balancer
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/ssl:/etc/nginx/ssl
    depends_on:
      - api
    restart: unless-stopped

  # PostgreSQL - База данных
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis - Очереди и кэш
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # MinIO - Object Storage
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped

  # FastAPI - API Server
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      JWT_SECRET: ${JWT_SECRET}
    volumes:
      - ./app:/app/app
      - ./uploads:/app/uploads
    depends_on:
      - postgres
      - redis
      - minio
    restart: unless-stopped

  # Celery Worker - Обработчик задач
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ./app:/app/app
      - ./uploads:/app/uploads
    depends_on:
      - postgres
      - redis
      - minio
    restart: unless-stopped
    deploy:
      replicas: 3

  # Celery Beat - Планировщик задач
  beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.queue.celery_app beat
    environment:
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./app:/app/app
    depends_on:
      - redis
    restart: unless-stopped

  # Flower - Мониторинг Celery
  flower:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.queue.celery_app flower --port=5555
    environment:
      REDIS_URL: redis://redis:6379/0
    ports:
      - "5555:5555"
    depends_on:
      - redis
    restart: unless-stopped

  # Prometheus - Сбор метрик
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  # Grafana - Дашборды
  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
  prometheus_data:
  grafana_data:
```

## Production развертывание

### Требования к серверу

- CPU: 4+ cores
- RAM: 16GB+
- Storage: 100GB+ SSD
- Ubuntu 22.04 LTS (рекомендуется)

### Шаги развертывания

#### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker и Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. Настройка SSL сертификатов (Let's Encrypt)

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx -y

# Получение сертификата
sudo certbot --nginx -d api.yourdomain.com

# Автоматическое обновление
sudo crontab -e
# Добавить: 0 0 * * * certbot renew --quiet
```

#### 3. Настройка Nginx

```nginx
# /etc/nginx/sites-available/ffmpeg-api
upstream api_backend {
    least_conn;
    server api:8000;
    server api:8001;
    server api:8002;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 1G;

    location / {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    location /metrics {
        proxy_pass http://prometheus:9090/metrics;
    }

    location /grafana/ {
        proxy_pass http://grafana:3000/;
    }
}
```

#### 4. Настройка .env для production

```bash
# .env.production
POSTGRES_DB=ffmpeg_prod
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=very_strong_password_here

REDIS_URL=redis://redis:6379/0

MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=very_strong_minio_password

JWT_SECRET=very_long_random_jwt_secret_here_minimum_32_characters

GRAFANA_ADMIN_PASSWORD=grafana_admin_password

# Production settings
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=1073741824
STORAGE_RETENTION_DAYS=7
WORKER_CONCURRENCY=4
```

#### 5. Запуск в production режиме

```bash
# Сборка production образов
docker-compose -f docker-compose.prod.yml build

# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker-compose ps
```

## Масштабирование

### Горизонтальное масштабирование API

```bash
# Увеличение количества API инстансов
docker-compose up -d --scale api=5
```

### Горизонтальное масштабирование Workers

```bash
# Увеличение количества workers
docker-compose up -d --scale worker=10
```

### Настройка автоматического масштабирования

```yaml
# docker-compose.autoscale.yml
version: '3.8'

services:
  worker:
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
      update_config:
        parallelism: 2
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

## Мониторинг и логирование

### Prometheus Configuration

```yaml
# docker/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'celery'
    static_configs:
      - targets: ['worker:5555']
```

### Grafana Dashboards

1. Дашборд производительности задач
2. Дашборд использования ресурсов
3. Дашборд ошибок
4. Дашборд очереди задач

### Логирование

```python
# app/monitoring/logger.py
import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
```

## Резервное копирование

Для резервного копирования и восстановления предоставлены готовые скрипты в директории `scripts/`:

### Backup скрипт

Полный функциональный скрипт резервного копирования (`scripts/backup.sh`):

```bash
# Базовое использование
./scripts/backup.sh

# С определенным типом (manual, scheduled, pre-deploy)
./scripts/backup.sh --type scheduled

# С ограничением количества хранимых бэкапов
./scripts/backup.sh --keep 7

# Пропустить определенные компоненты
./scripts/backup.sh --skip-minio --skip-config

# Не сжимать бэкап
./scripts/backup.sh --no-compress
```

**Что включает бэкап:**
- PostgreSQL database dump
- MinIO data files
- Environment configuration
- Docker Compose files
- Prometheus/Grafana configurations
- Git state information

### Restore скрипт

Полный функциональный скрипт восстановления (`scripts/restore.sh`):

```bash
# Восстановление из последнего бэкапа
./scripts/restore.sh

# Восстановление из конкретного бэкапа
./scripts/restore.sh pre-deploy_20250205_120000.tar.gz

# Пропустить определенные компоненты
./scripts/restore.sh --skip-config --skip-minio

# Пропустить запуск сервисов и health check
./scripts/restore.sh --skip-services-start --skip-health-check
```

### Автоматический backup через cron

```bash
# Добавить в crontab
0 2 * * * /path/to/scripts/backup.sh --type scheduled --keep 30
```

### Health Check скрипт

Полный функциональный скрипт проверки здоровья всех сервисов (`scripts/health_check.sh`):

```bash
# Базовая проверка здоровья
./scripts/health_check.sh

# Подробный вывод
./scripts/health_check.sh --verbose

# Быстрая проверка (5 попыток)
./scripts/health_check.sh --quick

# С кастомным URL
./scripts/health_check.sh --url https://api.yourdomain.com/api/v1/health
```

**Проверяемые сервисы:**
- PostgreSQL
- Redis
- MinIO
- API
- Celery Worker
- Flower
- Prometheus
- Grafana

## CI/CD Pipeline

### GitHub Actions Workflow

Проект включает полные CI/CD pipelines:

#### CI Pipeline (`.github/workflows/ci.yml`)

Запускается при:
- Push на ветки `main` и `develop`
- Pull Request на эти ветки
- Ручной запуск (workflow_dispatch)

**Jobs:**

1. **Linting** - Проверка кода:
   - Black (форматирование)
   - Flake8 (стиль кода)
   - MyPy (типизация)

2. **Tests** - Тестирование:
   - Pytest с coverage > 80%
   - Сервисы: PostgreSQL, Redis
   - Генерация HTML отчетов
   - Upload на Codecov

3. **Build** - Сборка Docker образов:
   - Multi-stage builds
   - Push в GitHub Container Registry
   - Кэширование слоев

4. **Security Scan** - Сканер безопасности:
   - Trivy vulnerability scanner
   - Upload результатов в GitHub Security

5. **Notifications** - Уведомления:
   - Успешное завершение
   - Ошибки и сбои

#### Deploy Pipeline (`.github/workflows/deploy.yml`)

Запускается при:
- Push на `main` (production)
- Ручной запуск (workflow_dispatch)

**Jobs:**

1. **Deploy to Production**:
   - Pre-deployment backup
   - SSH соединение с сервером
   - Pull кода
   - Pull Docker образов
   - Stop старых контейнеров
   - Database migrations
   - Start новых контейнеров
   - Health checks
   - Cleanup старых образов
   - Notifications (success/failure)

2. **Deploy to Staging** (опционально):
   - Те же шаги для staging окружения

3. **Rollback** (автоматически при ошибке):
   - Возврат к предыдущей версии
   - Уведомления

### Требуемые GitHub Secrets

Настроить в Settings > Secrets and variables > Actions:

```
# Production
PRODUCTION_HOST=your-server.com
PRODUCTION_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...
DEPLOY_USER=deploy

# Staging (опционально)
STAGING_HOST=staging.your-server.com
STAGING_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...

# Codecov (опционально)
CODECOV_TOKEN=your-codecov-token
```

## Обновление

### Автоматическое развертывание

Используйте готовый скрипт деплоя (`scripts/deploy.sh`):

```bash
# Полный процесс деплоя
./scripts/deploy.sh

# Пропустить pre-deployment backup
./scripts/deploy.sh --skip-backup

# Пропустить health check после деплоя
./scripts/deploy.sh --skip-health-check
```

**Что делает скрипт деплоя:**
1. Проверка зависимостей (Docker, Docker Compose, Git)
2. Загрузка переменных окружения
3. Создание pre-deployment backup
4. Pull последнего кода из репозитория
5. Сборка Docker образов
6. Остановка старых контейнеров
7. Запуск database migrations
8. Запуск новых контейнеров
9. Health checks
10. Очистка старых Docker образов
11. Показ сводки деплоя

### Manual Zero Downtime Deployment

```bash
# 1. Backup текущей версии
./scripts/backup.sh --type pre-deploy

# 2. Pull новых изменений
git pull origin main

# 3. Build новых образов
docker-compose build

# 4. Pull новых образов (для production)
docker-compose pull

# 5. Rollout обновления API
docker-compose up -d --no-deps api

# 6. Проверка здоровья
./scripts/health_check.sh

# 7. Обновление workers
docker-compose up -d --no-deps worker

# 8. Обновление других сервисов
docker-compose up -d beat flower
```

### Rollback

При проблемах с деплоем используйте скрипт отката:

```bash
# Автоматический откат к предыдущей версии
./scripts/rollback.sh

# Откат к конкретному тегу
./scripts/rollback.sh --to-tag rollback_point_20250205_120000

# Skip health check после отката
./scripts/rollback.sh --skip-health-check
```

**Что делает скрипт отката:**
1. Backup текущей версии перед откатом
2. Получение предыдущего коммита или тега
3. Checkout предыдущей версии
4. Пересборка и перезапуск контейнеров
5. Откат database migrations
6. Health checks
7. Показ сводки отката

## Troubleshooting

### Проверка логов

```bash
# API логи
docker-compose logs -f api

# Worker логи
docker-compose logs -f worker

# Все логи
docker-compose logs -f
```

### Проверка статуса очереди

```bash
# Войти в контейнер
docker-compose exec worker bash

# Запустить Celery shell
celery -A app.queue.celery_app shell

# Проверить активные задачи
from app.queue.celery_app import app
app.control.inspect().active()
```

### Перезапуск сервисов

```bash
# Все сервисы
docker-compose restart

# Определенный сервис
docker-compose restart api
docker-compose restart worker
```

### Очистка ресурсов

```bash
# Остановка и удаление контейнеров
docker-compose down

# Удаление volumes
docker-compose down -v

# Полная очистка
docker system prune -a
```

## Безопасность

### Настройка firewall

```bash
# Разрешить только необходимые порты
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### Настройка rate limiting в Nginx

```nginx
# Добавить в http блок
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# В location блок
limit_req zone=api_limit burst=20 nodelay;
```

## Performance Tuning

### Оптимизация PostgreSQL

```sql
-- postgresql.conf
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB
```

### Оптимизация Redis

```bash
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Мониторинг здоровья

### Health check endpoint

```python
# app/api/v1/health.py
from fastapi import APIRouter
from app.database.connection import database
from app.storage.minio_client import minio_client
from redis import Redis

router = APIRouter()

@router.get("/health")
async def health_check():
    health = {
        "status": "healthy",
        "components": {}
    }

    # Check database
    try:
        await database.connect()
        await database.execute("SELECT 1")
        health["components"]["database"] = "healthy"
    except Exception as e:
        health["components"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "unhealthy"

    # Check MinIO
    try:
        minio_client.list_buckets()
        health["components"]["storage"] = "healthy"
    except Exception as e:
        health["components"]["storage"] = f"unhealthy: {str(e)}"
        health["status"] = "unhealthy"

    # Check Redis
    try:
        redis = Redis.from_url("redis://redis:6379/0")
        redis.ping()
        health["components"]["cache"] = "healthy"
    except Exception as e:
        health["components"]["cache"] = f"unhealthy: {str(e)}"
        health["status"] = "unhealthy"

    return health
```

### Автоматический health check

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```
