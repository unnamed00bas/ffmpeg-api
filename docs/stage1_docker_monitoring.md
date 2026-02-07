# Этап 1.4: Docker окружение и мониторинг

## Обзор

Документация по настройке и использованию мониторинга для проекта FFmpeg-API. Используется стек Prometheus + Grafana для сбора метрик и визуализации данных.

---

## 1. Prometheus - Сбор метрик

### Конфигурация

**Файл:** `docker/prometheus.yml`

Prometheus настроен для сбора метрик со следующих сервисов:

| Job Name | Target | Port | Path | Описание |
|----------|--------|------|------|----------|
| `fastapi` | `api:8000` | 8000 | `/metrics` | Метрики FastAPI приложения |
| `postgres` | `postgres-exporter:9187` | 9187 | `/metrics` | Метрики PostgreSQL |
| `redis` | `redis-exporter:9121` | 9121 | `/metrics` | Метрики Redis |
| `celery-flower` | `flower:5555` | 5555 | `/metrics` | Метрики Celery (через Flower) |
| `prometheus` | `localhost:9090` | 9090 | - | Сам Prometheus |
| `node` | `node-exporter:9100` | 9100 | `/metrics` | Системные метрики хоста |

### Retention Policy

- **Время хранения:** 30 дней
- **Путь хранения:** `/prometheus` (volume `prometheus_data`)

### Доступ

- **Web UI:** http://localhost:9090
- **API:** http://localhost:9090/api/v1/

---

## 2. Grafana - Визуализация метрик

### Конфигурация

**Datasource конфигурация:** `docker/grafana/datasources/prometheus.yml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
    jsonData:
      timeInterval: 5s
      queryTimeout: 60s
```

### Дашборды

#### 2.1 API Performance Dashboard

**UID:** `api_performance`  
**Файл:** `docker/grafana/dashboards/api_performance.json`  
**Описание:** Мониторинг производительности FastAPI API

**Метрики:**
- **Requests per Second** - Количество запросов в секунду по endpoint'ам
- **Response Time (p95)** - Время ответа 95-го перцентиля
- **Response Time Percentiles (p50, p95, p99)** - Время ответа по перцентилям
- **Error Rate by Status Code** - Процент ошибок по кодам (4xx, 5xx)
- **Total Requests by Status Code** - Общее количество запросов по статусу

**Используемые Prometheus queries:**
```promql
# Requests per second
sum(rate(http_requests_total[5m])) by (endpoint)

# Response time percentiles
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))

# Error rate
sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint)
```

#### 2.2 System Resources Dashboard

**UID:** `system_resources`  
**Файл:** `docker/grafana/dashboards/system_resources.json`  
**Описание:** Мониторинг системных ресурсов контейнеров

**Метрики:**
- **CPU Utilization** - Загрузка CPU по контейнерам
- **RAM Usage (GB)** - Использование оперативной памяти
- **Network Traffic** - Сетевой трафик (RX/TX)
- **Disk I/O** - Дисковая операция (Read/Write)
- **Request Rate (Gauge)** - Текущий темп запросов
- **Requests Distribution by Status** - Распределение запросов по статусам

**Используемые Prometheus queries:**
```promql
# CPU utilization
cpu_usage_percent
rate(process_cpu_seconds_total[5m]) * 100

# Memory usage
memory_usage_bytes / 1024 / 1024 / 1024
redis_memory_used_bytes / 1024 / 1024 / 1024

# Network traffic
rate(node_network_receive_bytes_total[5m]) * 8
rate(node_network_transmit_bytes_total[5m]) * 8

# Disk I/O
rate(node_disk_read_bytes_total[5m])
rate(node_disk_written_bytes_total[5m])
```

#### 2.3 Celery Tasks Dashboard

**UID:** `celery_tasks`  
**Файл:** `docker/grafana/dashboards/celery_tasks.json`  
**Описание:** Мониторинг Celery задач и воркеров

**Метрики:**
- **Queue Size** - Размер очереди (pending, processing, failed)
- **Active Workers** - Количество активных воркеров
- **Task Duration (p50, p95, p99)** - Длительность задач по перцентилям
- **Success/Failure Rate** - Уровень успеха/отказов задач
- **Tasks Distribution by Status** - Распределение задач по статусам
- **Tasks Distribution by Type** - Распределение задач по типам
- **File Size Distribution** - Распределение размеров файлов

**Используемые Prometheus queries:**
```promql
# Queue size
queue_size{status="pending"}
queue_size{status="processing"}
queue_size{status="failed"}

# Active workers
active_workers

# Task duration percentiles
histogram_quantile(0.50, sum(rate(ffmpeg_task_duration_seconds_bucket[5m])) by (le, type))
histogram_quantile(0.95, sum(rate(ffmpeg_task_duration_seconds_bucket[5m])) by (le, type))
histogram_quantile(0.99, sum(rate(ffmpeg_task_duration_seconds_bucket[5m])) by (le, type))

# Success/Failure rate
sum(rate(ffmpeg_tasks_total{status="completed"}[5m])) by (type) / sum(rate(ffmpeg_tasks_total[5m])) by (type)
```

### Доступ

- **Web UI:** http://localhost:3000
- **Login:** `admin`
- **Password:** `admin` (можно изменить через переменную окружения `GRAFANA_ADMIN_PASSWORD`)

---

## 3. Docker Compose Сервисы

### Экспортеры метрик

#### PostgreSQL Exporter
```yaml
postgres-exporter:
  image: prometheuscommunity/postgres-exporter:latest
  ports:
    - "9187:9187"
  environment:
    DATA_SOURCE_NAME: "postgresql://postgres_user:postgres_password@postgres:5432/ffmpeg_api?sslmode=disable"
```

#### Redis Exporter
```yaml
redis-exporter:
  image: oliver006/redis_exporter:latest
  ports:
    - "9121:9121"
  environment:
    REDIS_ADDR: redis://redis:6379
```

#### Node Exporter
```yaml
node-exporter:
  image: prom/node-exporter:latest
  ports:
    - "9100:9100"
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /:/rootfs:ro
```

### Prometheus Service
```yaml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus_data:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=30d'
```

### Grafana Service
```yaml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./docker/grafana/provisioning:/etc/grafana/provisioning
    - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
    - ./docker/grafana/datasources:/etc/grafana/provisioning/datasources
  environment:
    GF_SECURITY_ADMIN_PASSWORD: admin
    GF_USERS_ALLOW_SIGN_UP: "false"
    GF_SERVER_ROOT_URL: http://localhost:3000
```

### Flower Service
```yaml
flower:
  build:
    context: .
    dockerfile: docker/Dockerfile.worker
  command: celery -A app.queue.celery_app flower --port=5555
  ports:
    - "5555:5555"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5555"]
```

---

## 4. Метрики приложения

### Определённые метрики в `app/monitoring/metrics.py`

| Метрика | Тип | Описание | Лейблы |
|---------|-----|----------|--------|
| `http_requests_total` | Counter | Всего HTTP запросов | method, endpoint, status_code |
| `http_request_duration_seconds` | Histogram | Время обработки запросов | method, endpoint |
| `ffmpeg_tasks_total` | Counter | Всего FFmpeg задач | type, status |
| `ffmpeg_task_duration_seconds` | Histogram | Время обработки FFmpeg задач | type |
| `file_size_bytes` | Histogram | Размер файлов | type (input/output) |
| `queue_size` | Gauge | Размер очереди задач | status (pending/processing/failed) |
| `active_workers` | Gauge | Активные воркеры | - |
| `cpu_usage_percent` | Gauge | Использование CPU | - |
| `memory_usage_bytes` | Gauge | Использование памяти | - |

### Использование метрик в коде

```python
from app.monitoring.metrics import (
    track_task_created,
    track_task_started,
    track_task_completed,
    track_task_failed,
    track_file_size
)

# Создание задачи
track_task_created(task_type="join")

# Начало обработки
track_task_started(task_type="join")

# Завершение задачи
track_task_completed(task_type="join", duration=45.5)

# Ошибка задачи
track_task_failed(task_type="join", duration=30.2)

# Отслеживание размера файла
track_file_size(file_type="input", size=10485760)  # 10MB
```

---

## 5. Запуск и тестирование

### Запуск всех сервисов

```bash
docker-compose up -d
```

### Проверка статуса сервисов

```bash
docker-compose ps
```

### Проверка health checks

```bash
# PostgreSQL
docker-compose exec postgres pg_isready -U postgres_user

# Redis
docker-compose exec redis redis-cli ping

# API
curl http://localhost:8000/api/v1/health

# Prometheus
curl http://localhost:9090/-/healthy

# Grafana
curl http://localhost:3000/api/health

# Flower
curl http://localhost:5555
```

### Проверка сбора метрик

```bash
# FastAPI метрики
curl http://localhost:8000/metrics

# PostgreSQL экспортер
curl http://localhost:9187/metrics

# Redis экспортер
curl http://localhost:9121/metrics

# Node экспортер
curl http://localhost:9100/metrics
```

---

## 6. Мониторинг через веб-интерфейсы

### Prometheus UI (http://localhost:9090)

1. **Status → Targets** - Проверка статуса всех scrape targets
2. **Graph** - Выполнение Prometheus queries
3. **Status → Configuration** - Просмотр текущей конфигурации

### Grafana UI (http://localhost:3000)

1. Войти с логином `admin` и паролем `admin`
2. Перейти в **Dashboards → Browse**
3. Открыть один из трёх дашбордов:
   - API Performance Dashboard
   - System Resources Dashboard
   - Celery Tasks Dashboard

### Flower UI (http://localhost:5555)

1. Просмотр активных задач
2. Мониторинг воркеров
3. Анализ результатов выполнения задач

---

## 7. Troubleshooting

### Prometheus не собирает метрики

1. Проверьте список targets в Prometheus UI: http://localhost:9090/targets
2. Убедитесь, что все контейнеры запущены: `docker-compose ps`
3. Проверьте логи контейнеров: `docker-compose logs prometheus`
4. Проверьте доступность endpoints:
   ```bash
   curl http://localhost:8000/metrics
   curl http://localhost:9187/metrics
   ```

### Grafana дашборды не загружаются

1. Проверьте provisioning конфигурацию в контейнере:
   ```bash
   docker-compose exec grafana ls -la /etc/grafana/provisioning/
   ```
2. Проверьте логи Grafana:
   ```bash
   docker-compose logs grafana
   ```
3. Перезапустите Grafana:
   ```bash
   docker-compose restart grafana
   ```

### Экспортеры недоступны

1. Проверьте health checks:
   ```bash
   docker-compose ps
   ```
2. Проверьте логи конкретного экспортера:
   ```bash
   docker-compose logs postgres-exporter
   docker-compose logs redis-exporter
   docker-compose logs node-exporter
   ```

---

## 8. Структура файлов

```
ffmpeg-api/
├── docker/
│   ├── prometheus.yml                    # Конфигурация Prometheus
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   └── dashboards.yml           # Provisioning конфигурация
│   │   ├── datasources/
│   │   │   └── prometheus.yml           # Datasource для Prometheus
│   │   └── dashboards/
│   │       ├── api_performance.json      # API Performance дашборд
│   │       ├── system_resources.json     # System Resources дашборд
│   │       └── celery_tasks.json        # Celery Tasks дашборд
│   ├── Dockerfile.api
│   └── Dockerfile.worker
├── app/
│   └── monitoring/
│       └── metrics.py                   # Определение метрик приложения
├── docker-compose.yml                   # Все сервисы включая мониторинг
└── docs/
    └── stage1_docker_monitoring.md      # Данная документация
```

---

## 9. Следующие шаги

1. **Настройка alerts** - Создать правила алертинга в Prometheus
2. **Уведомления** - Настроить отправку уведомлений (Slack, Email, Telegram)
3. **Дополнительные метрики** - Добавить метрики для бизнес-логики
4. **Исторические отчёты** - Настроить генерацию отчётов в Grafana
5. **Производительность** - Оптимизировать интервалы scrape и retention

---

## 10. Ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)
- [Flower Documentation](https://flower.readthedocs.io/)

---

**Дата создания:** 05.02.2026  
**Версия:** 1.0  
**Автор:** AI Assistant
