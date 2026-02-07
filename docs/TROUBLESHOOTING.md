# Руководство по устранению неполадок (Troubleshooting)

Данное руководство поможет вам диагностировать и решать распространенные проблемы при работе с FFmpeg API.

## Содержание

- [Common Issues and Solutions](#common-issues-and-solutions)
  - [Docker Container Issues](#docker-container-issues)
  - [Database Issues](#database-issues)
  - [FFmpeg Issues](#ffmpeg-issues)
  - [API Issues](#api-issues)
  - [MinIO Issues](#minio-issues)
  - [Redis Issues](#redis-issues)
- [Emergency Procedures](#emergency-procedures)
- [Monitoring and Debugging](#monitoring-and-debugging)

---

## Common Issues and Solutions

### Docker Container Issues

#### Проблема: Контейнеры не запускаются

**Симптомы:**
- `docker-compose up` не запускает контейнеры
- Контейнеры сразу останавливаются с ошибкой
- Сообщение "Exited with code X"

**Возможные причины:**
- Недостаточно ресурсов (RAM/Disk)
- Конфликты портов с другими сервисами
- Некорректная конфигурация в `.env`
- Отсутствие необходимых volumes

**Диагностика:**

```bash
# Проверка статуса всех контейнеров
docker-compose ps

# Просмотр логов конкретного контейнера
docker-compose logs api
docker-compose logs postgres
docker-compose logs redis
docker-compose logs worker

# Подробные логи с временными метками
docker-compose logs -f --tail=100 api

# Проверка использования ресурсов
docker stats

# Проверка доступности портов
netstat -ano | findstr "8000"
netstat -ano | findstr "5432"
netstat -ano | findstr "6379"

# Проверка дискового пространства
df -h
```

**Решения:**

```bash
# 1. Очистка и перезапуск
docker-compose down -v
docker-compose up -d

# 2. Проверка .env файла
# Убедитесь, что файл .env существует и содержит корректные значения
cat .env

# 3. Пересоздание образа
docker-compose build --no-cache api
docker-compose up -d api

# 4. Изменение портов в docker-compose.yml
# Если порт занят, измените маппинг портов:
# ports:
#   - "8001:8000"  # вместо 8000:8000

# 5. Проверка Docker ресурсов
# Windows: Docker Desktop -> Settings -> Resources
# Увеличьте память минимум до 8GB
```

#### Проблема: Конфликты портов

**Симптомы:**
- Ошибка "Bind for 0.0.0.0:PORT failed: port is already allocated"
- Сервис не доступен на ожидаемом порту

**Возможные причины:**
- Другое приложение использует тот же порт
- Предыдущий экземпляр контейнера не был остановлен
- Несколько экземпляров docker-compose

**Диагностика:**

```bash
# Проверка занятых портов
netstat -ano | findstr ":8000"
netstat -ano | findstr ":5432"
netstat -ano | findstr ":6379"
netstat -ano | findstr ":9000"

# Для Linux/Mac:
lsof -i :8000
lsof -i :5432
```

**Решения:**

```bash
# 1. Остановка всех контейнеров
docker-compose down

# 2. Остановка контейнеров, использующих порты
docker stop $(docker ps -q)

# 3. Убийство процессов, занимающих порты (Windows)
# Найдите PID из netstat, затем:
taskkill /PID <PID> /F

# 4. Изменение портов в docker-compose.yml
services:
  api:
    ports:
      - "8001:8000"  # Используйте другой порт хоста
  postgres:
    ports:
      - "5433:5432"
  redis:
    ports:
      - "6380:6379"
```

---

### Database Issues

#### Проблема: Connection refused / Не удается подключиться к базе данных

**Симптомы:**
- Ошибка "connection refused" или "could not connect to server"
- API не может подключиться к PostgreSQL
- Tasks застревают в статусе "pending"

**Возможные причины:**
- PostgreSQL контейнер не запущен
- Неверные учетные данные в DATABASE_URL
- База данных еще не инициализирована
- Network проблемы между контейнерами

**Диагностика:**

```bash
# Проверка статуса PostgreSQL
docker-compose ps postgres

# Просмотр логов PostgreSQL
docker-compose logs postgres

# Проверка здоровья базы данных
docker-compose exec postgres pg_isready -U postgres_user

# Прямое подключение к базе данных
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "\conninfo"

# Проверка таблиц
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "\dt"

# Проверка network connectivity
docker-compose exec api ping -c 3 postgres
docker-compose exec api curl postgres:5432

# Проверка переменных окружения
docker-compose exec api env | grep DATABASE
```

**Решения:**

```bash
# 1. Перезапуск PostgreSQL
docker-compose restart postgres

# Подождите 10-15 секунд для полной инициализации

# 2. Проверка и исправление учетных данных в .env
# Убедитесь, что значения совпадают:
# .env:
# POSTGRES_USER=postgres_user
# POSTGRES_PASSWORD=postgres_password
# POSTGRES_DB=ffmpeg_api

# DATABASE_URL в .env:
# DATABASE_URL=postgresql+asyncpg://postgres_user:postgres_password@postgres:5432/ffmpeg_api

# 3. Инициализация базы данных
docker-compose exec api python scripts/init_db.py

# 4. Запуск миграций
docker-compose exec api alembic upgrade head

# 5. Создание admin пользователя
docker-compose exec api python scripts/create_admin.py

# 6. Если база повреждена, пересоздайте (ПРЕДУПРЕЖДЕНИЕ: данные будут потеряны)
docker-compose down -v
docker-compose up -d postgres
# Подождите 15 секунд
docker-compose exec api alembic upgrade head
docker-compose exec api python scripts/create_admin.py
docker-compose up -d
```

#### Проблема: Migration problems

**Симптомы:**
- Ошибка при запуске миграций
- Таблицы отсутствуют или имеют неверную структуру
- "alembic.util.exc.CommandError"

**Возможные причины:**
- База данных не соответствует миграциям
- Некорректная версия alembic в базе данных
- Конфликт версий миграций

**Диагностика:**

```bash
# Проверка текущей версии миграции
docker-compose exec api alembic current

# Проверка истории миграций
docker-compose exec api alembic history

# Проверка таблицы alembic_version
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "SELECT * FROM alembic_version;"
```

**Решения:**

```bash
# 1. Обновление до последней версии
docker-compose exec api alembic upgrade head

# 2. Если версия не синхронизирована - сброс
docker-compose exec api alembic stamp head

# 3. Откат к предыдущей версии
docker-compose exec api alembic downgrade -1

# 4. Полная пересборка (ПРЕДУПРЕЖДЕНИЕ: потеря данных)
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker-compose exec api alembic stamp base
docker-compose exec api alembic upgrade head
```

---

### FFmpeg Issues

#### Проблема: FFmpeg not found

**Симптомы:**
- Ошибка "ffprobe not found" или "ffmpeg not found"
- Tasks не выполняются
- FileInfo не может получить метаданные видео

**Возможные причины:**
- FFmpeg не установлен в Docker образе
- Некорректный путь к FFmpeg в конфигурации
- FFmpeg не добавлен в PATH

**Диагностика:**

```bash
# Проверка наличия FFmpeg в контейнере API
docker-compose exec api which ffmpeg
docker-compose exec api which ffprobe

# Проверка версии FFmpeg
docker-compose exec api ffmpeg -version
docker-compose exec api ffprobe -version

# Проверка переменных окружения
docker-compose exec api env | grep FFMPEG

# Проверка в контейнере worker
docker-compose exec worker which ffmpeg
docker-compose exec worker ffmpeg -version
```

**Решения:**

```bash
# 1. Проверка Dockerfile.api и Dockerfile.worker
# Убедитесь, что FFmpeg установлен:

# В docker/Dockerfile.api:
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# В docker/Dockerfile.worker (та же команда)

# 2. Пересборка образов
docker-compose build --no-cache api worker
docker-compose up -d

# 3. Проверка пути в .env
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe

# 4. Ручная установка FFmpeg в запущенном контейнере (временно)
docker-compose exec api apt-get update && apt-get install -y ffmpeg
```

#### Проблема: Медленная обработка видео

**Симптомы:**
- Задачи выполняются очень долго
- High CPU usage
- Tasks timeout

**Возможные причины:**
- Недостаточно ресурсов (CPU/RAM)
- Некорректные настройки FFmpeg
- Слишком много одновременных задач
- Неоптимизированные параметры кодирования

**Диагностика:**

```bash
# Мониторинг ресурсов контейнеров
docker stats

# Проверка количества worker'ов
docker-compose ps | grep worker

# Проверка очереди Celery
docker-compose exec flower celery -A app.queue.celery_app inspect active

# Проверка текущих задач
docker-compose exec api python -c "from app.queue.celery_app import app; print(app.control.inspect().active())"
```

**Решения:**

```bash
# 1. Масштабирование worker'ов
docker-compose up -d --scale worker=4

# 2. Настройка параметров FFmpeg в .env
FFMPEG_THREADS=4
FFMPEG_PRESET=faster  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow

# 3. Изменение настроек Celery
CELERY_WORKER_CONCURRENCY=4  # Количество процессов на worker
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# 4. Изменение времени ожидания задач
CELERY_TASK_TIME_LIMIT=7200  # 2 часа
CELERY_TASK_SOFT_TIME_LIMIT=6000

# 5. Приоритизация важных задач
# Используйте priority при создании задачи
```

---

### API Issues

#### Проблема: 401 Unauthorized

**Симптомы:**
- API возвращает `{"detail": "Could not validate credentials"}`
- Не удается получить токен
- Токен быстро истекает

**Возможные причины:**
- Неверный JWT_SECRET
- Токен истек
- Неверные учетные данные пользователя
- Проблемы с timezone

**Диагностика:**

```bash
# Проверка переменных окружения
docker-compose exec api env | grep JWT

# Попытка получить токен
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Проверка времени в контейнере
docker-compose exec api date

# Проверка логов
docker-compose logs api | grep -i "jwt\|auth\|token"
```

**Решения:**

```bash
# 1. Проверка JWT_SECRET в .env
# Должен быть минимум 32 символа:
JWT_SECRET=your-secret-key-change-this-in-production-minimum-32-characters

# 2. Перезапуск API после изменения .env
docker-compose restart api

# 3. Увеличение времени жизни токена в .env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# 4. Создание нового admin пользователя
docker-compose exec api python scripts/create_admin.py

# 5. Получение нового токена
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

#### Проблема: 500 Internal Server Error

**Симптомы:**
- API возвращает HTTP 500
- Задачи завершаются с ошибкой
- Непредсказуемое поведение

**Возможные причины:**
- Исключение в коде приложения
- Некорректные входные данные
- Проблемы с зависимостями
- Недостаточно ресурсов

**Диагностика:**

```bash
# Просмотр логов API
docker-compose logs -f --tail=100 api

# Просмотр логов worker
docker-compose logs -f --tail=100 worker

# Проверка health endpoint
curl http://localhost:8000/api/v1/health

# Подробный режим (измените DEBUG=True в .env)
# Затем перезапустите:
docker-compose restart api
```

**Решения:**

```bash
# 1. Включение режима отладки
# В .env:
DEBUG=True
LOG_LEVEL=DEBUG

# 2. Перезапуск API
docker-compose restart api

# 3. Проверка последних ошибок в логах
docker-compose logs api | grep -i "error\|exception\|traceback"

# 4. Проверка подключения к базе данных
docker-compose exec api python -c "from app.database.session import engine; import asyncio; asyncio.run(engine.connect())"

# 5. Проверка зависимостей
docker-compose exec api pip list

# 6. Переустановка зависимостей
docker-compose exec api pip install -r requirements.txt
```

---

### MinIO Issues

#### Проблема: Connection errors / Upload failures

**Симптомы:**
- Ошибка "Failed to upload file"
- "Connection refused" при подключении к MinIO
- Файлы не сохраняются в хранилище

**Возможные причины:**
- MinIO контейнер не запущен
- Неверные учетные данные
- Bucket не создан
- Network проблемы

**Диагностика:**

```bash
# Проверка статуса MinIO
docker-compose ps minio

# Просмотр логов MinIO
docker-compose logs minio

# Проверка здоровья MinIO
docker-compose exec minio curl -f http://localhost:9000/minio/health/live

# Проверка подключения к MinIO консоли
curl http://localhost:9001

# Проверка переменных окружения
docker-compose exec api env | grep MINIO

# Тест подключения через mc (MinIO Client)
docker run --rm -it --network ffmpeg-ffmpeg-network minio/mc \
  alias set local http://minio:9000 minioadmin minioadmin
docker run --rm --network ffmpeg-ffmpeg-network minio/mc ls local/
```

**Решения:**

```bash
# 1. Перезапуск MinIO
docker-compose restart minio

# 2. Проверка учетных данных в .env
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET_NAME=ffmpeg-files

# Те же данные должны быть в контейнере API:
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# 3. Создание bucket через MinIO Client
docker run --rm --network ffmpeg-ffmpeg-network minio/mc \
  alias set local http://minio:9000 minioadmin minioadmin
docker run --rm --network ffmpeg-ffmpeg-network minio/mc mb local/ffmpeg-files

# 4. Проверка прав доступа к bucket
docker run --rm --network ffmpeg-ffmpeg-network minio/mc \
  policy set download local/ffmpeg-files

# 5. Пересоздание MinIO (ПРЕДУПРЕЖДЕНИЕ: потеря данных)
docker-compose down -v
docker-compose up -d minio
# Создание bucket
docker run --rm --network ffmpeg-ffmpeg-network minio/mc \
  alias set local http://minio:9000 minioadmin minioadmin
docker run --rm --network ffmpeg-ffmpeg-network minio/mc mb local/ffmpeg-files
```

---

### Redis Issues

#### Проблема: Connection refused

**Симптомы:**
- Ошибка "Error connecting to Redis"
- Celery worker не может подключиться
- Tasks не обрабатываются

**Возможные причины:**
- Redis контейнер не запущен
- Неверный порт или хост
- Network проблемы

**Диагностика:**

```bash
# Проверка статуса Redis
docker-compose ps redis

# Просмотр логов Redis
docker-compose logs redis

# Проверка здоровья Redis
docker-compose exec redis redis-cli ping
# Должен вернуть: PONG

# Проверка подключения из API контейнера
docker-compose exec api redis-cli -h redis ping

# Проверка переменных окружения
docker-compose exec api env | grep REDIS
docker-compose exec api env | grep CELERY
```

**Решения:**

```bash
# 1. Перезапуск Redis
docker-compose restart redis

# 2. Проверка конфигурации в .env
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 3. Проверка network connectivity
docker-compose exec api ping -c 3 redis

# 4. Если Redis поврежден - очистка и перезапуск
docker-compose exec redis redis-cli FLUSHALL
docker-compose restart redis
```

#### Проблема: Memory issues

**Симптомы:**
- Redis использует слишком много памяти
- Ошибки "OOM command not allowed"
- Медленная работа

**Возможные причины:**
- Слишком много кэшированных данных
- Некорректная политика очистки памяти
- Большая очередь задач

**Диагностика:**

```bash
# Проверка использования памяти Redis
docker-compose exec redis redis-cli INFO memory

# Проверка размера базы данных
docker-compose exec redis redis-cli DBSIZE

# Проверка текущих настроек памяти
docker-compose exec redis redis-cli CONFIG GET maxmemory
docker-compose exec redis redis-cli CONFIG GET maxmemory-policy

# Проверка Celery queues
docker-compose exec redis redis-cli KEYS "celery*"
```

**Решения:**

```bash
# 1. Изменение настроек памяти в docker-compose.yml
services:
  redis:
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    # Вместо 1gb используйте 2gb или больше
    # allkeys-lru - удаляет наименее используемые ключи

# 2. Перезапуск Redis с новыми настройками
docker-compose up -d redis

# 3. Очистка кэша (см. раздел Emergency Procedures)
docker-compose exec redis redis-cli FLUSHDB
# Очистка всех баз данных:
docker-compose exec redis redis-cli FLUSHALL

# 4. Настройка TTL для кэшированных данных
# В коде приложения:
# cache.set("key", value, timeout=3600)  # 1 час TTL
```

---

## Emergency Procedures

### Сброс базы данных

**⚠️ ПРЕДУПРЕЖДЕНИЕ: Эта процедура удалит все данные из базы данных!**

Используйте только в крайних случаях, когда база данных повреждена и не может быть восстановлена.

```bash
# 1. Остановка всех сервисов
docker-compose down

# 2. Удаление volumes (удаляет все данные базы данных)
docker volume rm ffmpeg-api_postgres_data

# 3. Запуск PostgreSQL
docker-compose up -d postgres

# 4. Ожидание полной инициализации (15-20 секунд)
docker-compose exec postgres pg_isready -U postgres_user

# 5. Применение миграций
docker-compose exec api alembic upgrade head

# 6. Создание admin пользователя
docker-compose exec api python scripts/create_admin.py

# 7. Запуск остальных сервисов
docker-compose up -d
```

### Очистка кэша Redis

```bash
# Очистка текущей базы данных (db 0)
docker-compose exec redis redis-cli FLUSHDB

# Очистка всех баз данных
docker-compose exec redis redis-cli FLUSHALL

# Очистка Celery специфических ключей
docker-compose exec redis redis-cli --scan --pattern "celery*" | xargs redis-cli DEL

# После очистки перезапустите worker'ов
docker-compose restart worker beat
```

### Очистка очереди Celery

```bash
# 1. Остановите worker'ы
docker-compose stop worker beat

# 2. Удалите все задачи из очереди
docker-compose exec redis redis-cli --scan --pattern "celery*" | xargs redis-cli DEL

# 3. Очистите результаты задач
docker-compose exec redis redis-cli --scan --pattern "celery-task-meta*" | xargs redis-cli DEL

# 4. Перезапустите worker'ы
docker-compose start worker beat
```

### Перезапуск сервисов

```bash
# Перезапуск всех сервисов
docker-compose restart

# Перезапуск конкретного сервиса
docker-compose restart api
docker-compose restart worker
docker-compose restart postgres

# Полный перезапуск (остановка + запуск)
docker-compose down
docker-compose up -d

# Пересборка и перезапуск
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Monitoring and Debugging

### Проверка логов

```bash
# Все логи всех сервисов
docker-compose logs

# Логи конкретного сервиса
docker-compose logs api
docker-compose logs worker
docker-compose logs postgres
docker-compose logs redis
docker-compose logs minio

# Следить за логами в реальном времени
docker-compose logs -f api
docker-compose logs -f worker

# Последние N строк логов
docker-compose logs --tail=50 api
docker-compose logs --tail=100 worker

# Логи с временными метками
docker-compose logs -t api

# Логи нескольких сервисов одновременно
docker-compose logs -f api worker

# Фильтрация логов (grep)
docker-compose logs api | grep -i "error"
docker-compose logs worker | grep -i "exception"
docker-compose logs api | grep -i "traceback"

# Сохранение логов в файл
docker-compose logs api > api_logs.txt
```

### Мониторинг ресурсов

```bash
# Текущее использование ресурсов всех контейнеров
docker stats

# Форматированный вывод
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Статистика для конкретного контейнера
docker stats ffmpeg-api

# Нетерминальный режим (для скриптов)
docker stats --no-stream

# Статистика контейнеров по шаблону имени
docker stats --filter "name=ffmpeg-worker*"

# Проверка использования диска
docker system df

# Проверка размера контейнеров и images
docker system df -v

# Проверка disk usage в контейнере
docker-compose exec api df -h
docker-compose exec api du -sh /app/temp/*
```

### Проверка статуса сервисов

```bash
# Статус всех сервисов
docker-compose ps

# Подробный статус
docker-compose ps -a

# Проверка здоровья сервисов (healthcheck)
docker-compose ps
# В колонке State должно быть "Up (healthy)"

# Проверка статуса конкретного сервиса
docker-compose ps api
docker-compose ps postgres
docker-compose ps redis

# Проверка health endpoints
curl http://localhost:8000/api/v1/health

# Проверка MinIO health
curl http://localhost:9000/minio/health/live

# Проверка PostgreSQL
docker-compose exec postgres pg_isready -U postgres_user

# Проверка Redis
docker-compose exec redis redis-cli ping

# Проверка Celery workers
docker-compose exec flower curl http://localhost:5555
```

### Анализ производительности

```bash
# 1. Используйте Grafana для визуальной оценки метрик
# URL: http://localhost:3000
# Login: admin / admin

# Доступные дашборды:
# - API Performance
# - Celery Tasks
# - Error Rates
# - Queue Size
# - System Resources
# - Task Performance

# 2. Prometheus для сырых метрик
# URL: http://localhost:9090

# 3. Flower для мониторинга Celery
# URL: http://localhost:5555
# Показывает:
# - Активные задачи
# - Очереди задач
# - Worker'ы
# - Успешные/неудачные задачи
# - Время выполнения задач

# 4. Проверка очереди задач через CLI
docker-compose exec redis redis-cli --scan --pattern "celery*" | wc -l

# 5. Информация о задачах
docker-compose exec worker celery -A app.queue.celery_app inspect active
docker-compose exec worker celery -A app.queue.celery_app inspect registered
docker-compose exec worker celery -A app.queue.celery_app inspect stats

# 6. Профилирование API (для выявления медленных endpoints)
# Установите DEBUG=True в .env и включите middleware для профилирования
# Или используйте встроенные метрики Prometheus
```

### Полезные команды для каждой категории

#### Docker Commands

```bash
# Просмотр всех контейнеров
docker ps -a

# Убийство зависших контейнеров
docker kill $(docker ps -q)

# Очистка неиспользуемых ресурсов
docker system prune
docker system prune -a  # более агрессивная очистка
docker system prune -a --volumes  # включает volumes

# Вход в контейнер для отладки
docker-compose exec api bash
docker-compose exec worker bash
docker-compose exec postgres bash

# Выполнение команды в контейнере
docker-compose exec api python --version
docker-compose exec postgres psql --version
```

#### Database Commands

```bash
# Подключение к PostgreSQL
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api

# SQL команды внутри psql:
\l                    # список баз данных
\c ffmpeg_api         # подключение к базе
\dt                   # список таблиц
\d table_name         # структура таблицы
\du                   # список пользователей
\q                    # выход

# Бэкап базы данных
docker-compose exec postgres pg_dump -U postgres_user ffmpeg_api > backup.sql

# Восстановление из бэкапа
docker-compose exec -T postgres psql -U postgres_user ffmpeg_api < backup.sql

# Создание бэкапа через Docker
docker exec ffmpeg-postgres pg_dump -U postgres_user ffmpeg_api > backup.sql
```

#### Redis Commands

```bash
# Интерактивная консоль Redis
docker-compose exec redis redis-cli

# Команды внутри redis-cli:
INFO                  # общая информация
INFO memory           # информация о памяти
INFO stats            # статистика
KEYS *                # все ключи
GET key               # получить значение
SET key value         # установить значение
DEL key               # удалить ключ
EXPIRE key seconds    # установить TTL
TTL key               # оставшееся время TTL
DBSIZE                # количество ключей
MONITOR               # мониторинг команд в реальном времени
SLOWLOG               # медленные запросы

# Команды для Celery:
KEYS celery*          # все ключи Celery
LLEN celery           # размер очереди celery
LRANGE celery 0 10    # первые 10 задач в очереди
```

#### Celery Commands

```bash
# Проверка активных задач
docker-compose exec worker celery -A app.queue.celery_app inspect active

# Проверка зарегистрированных задач
docker-compose exec worker celery -A app.queue.celery_app inspect registered

# Статистика worker'ов
docker-compose exec worker celery -A app.queue.celery_app inspect stats

# Проверка очередей
docker-compose exec worker celery -A app.queue.celeryapp inspect active_queues

# Очистка очереди (через worker)
docker-compose exec worker celery -A app.queue.celery_app purge

# Мониторинг через Flower
# Доступно на http://localhost:5555
```

#### MinIO Commands

```bash
# Использование MinIO Client
# Создание alias
docker run --rm -it --network ffmpeg-ffmpeg-network minio/mc \
  alias set local http://minio:9000 minioadmin minioadmin

# Список buckets
docker run --rm --network ffmpeg-ffmpeg-network minio/mc ls local/

# Список файлов в bucket
docker run --rm --network ffmpeg-ffmpeg-network minio/mc ls local/ffmpeg-files/

# Загрузка файла
docker run --rm --network ffmpeg-ffmpeg-network -v $(pwd):/data minio/mc \
  cp /data/test.mp4 local/ffmpeg-files/

# Скачивание файла
docker run --rm --network ffmpeg-ffmpeg-network -v $(pwd):/data minio/mc \
  cp local/ffmpeg-files/test.mp4 /data/

# Удаление файла
docker run --rm --network ffmpeg-ffmpeg-network minio/mc \
  rm local/ffmpeg-files/test.mp4

# Настройка политики доступа
docker run --rm --network ffmpeg-ffmpeg-network minio/mc \
  policy set download local/ffmpeg-files
```

---

## Дополнительные ресурсы

### Документация

- [Документация API](API.md)
- [Архитектура системы](ARCHITECTURE.md)
- [Руководство по развертыванию](DEPLOYMENT.md)
- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

### Мониторинг

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Flower**: http://localhost:5555
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### Полезные ссылки

- Docker Troubleshooting: https://docs.docker.com/engine/troubleshooting/
- PostgreSQL Troubleshooting: https://www.postgresql.org/docs/current/troubleshooting.html
- Redis Troubleshooting: https://redis.io/docs/management/troubleshooting/
- MinIO Troubleshooting: https://min.io/docs/minio/linux/operations/troubleshooting.html

---

## Получение помощи

Если вы не смогли решить проблему с помощью этого руководства:

1. Соберите необходимую информацию:
   - Полные логи проблемных сервисов
   - Версии Docker и Docker Compose
   - Конфигурацию `.env` (скройте секреты)
   - Системные ресурсы (RAM, Disk)

2. Создайте issue в репозитории проекта с подробным описанием:
   - Шаги для воспроизведения
   - Ожидаемое поведение
   - Фактическое поведение
   - Логи и вывод команд

3. Приложите собранную информацию к issue для быстрого решения проблемы.

---

**Примечание:** При работе с командами, которые удаляют данные (FLUSHDB, FLUSHALL, DROP, DELETE), будьте предельно осторожны. Создавайте бэкапы перед выполнением разрушительных операций.
