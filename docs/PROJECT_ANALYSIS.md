# Анализ проекта FFmpeg API

## Обзор

FFmpeg API — это REST API сервис для асинхронной обработки видео с использованием FFmpeg, FastAPI, Celery и PostgreSQL.

---

## 📋 Что нужно доделать

### ✅ Готово

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Core API | ✅ | FastAPI, endpoints для обработки видео |
| Database | ✅ | PostgreSQL + Alembic миграции |
| Task Queue | ✅ | Celery + Redis |
| Object Storage | ✅ | MinIO (S3-compatible) |
| Docker | ✅ | Dockerfile.api, Dockerfile.worker |
| Docker Compose | ✅ | dev и production конфигурации |
| CI/CD | ✅ | GitHub Actions workflows |
| Мониторинг | ✅ | Prometheus + Grafana |
| Скрипты | ✅ | backup, restore, deploy, rollback, health_check |
| Тесты | ✅ | Unit, integration, e2e тесты |
| Документация | ✅ | API.md, DEPLOYMENT.md, ARCHITECTURE.md |

### ⚠️ Требует настройки/проверки

| Компонент | Статус | Что нужно сделать |
|-----------|--------|-------------------|
| **SSL сертификаты** | ⚠️ | Настроить Let's Encrypt на production сервере |
| **GitHub Secrets** | ⚠️ | Добавить все необходимые secrets (см. ниже) |
| **Production .env** | ⚠️ | Заполнить реальными значениями `.env.production` |
| **Nginx SSL** | ⚠️ | Создать сертификаты в `docker/nginx/ssl/` |
| **Домен** | ⚠️ | DNS записи и настройка домена |
| **Тестирование CI** | ⏳ | Прогнать CI pipeline для проверки |

---

## 🔄 Как работает автоматическое развёртывание

### CI Pipeline (`.github/workflows/ci.yml`)

**Триггеры:**
- Push на ветки `main` и `develop`
- Pull Request на эти ветки
- Ручной запуск (workflow_dispatch)

**Этапы:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Linting    │────▶│   Tests     │────▶│   Build     │────▶│  Security   │
│             │     │             │     │   Docker    │     │    Scan     │
│ - Black     │     │ - Pytest    │     │   Images    │     │ - Trivy     │
│ - isort     │     │ - Coverage  │     │             │     │             │
│ - Flake8    │     │   >80%      │     │ Push to     │     │ Upload to   │
│ - MyPy      │     │             │     │ GHCR        │     │ Security    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Deploy Pipeline (`.github/workflows/deploy.yml`)

**Триггеры:**
- Push на ветку `main` (автоматически → production)
- Ручной запуск с выбором environment (production/staging)

**Последовательность действий:**

```mermaid
flowchart TD
    A[Push на main] --> B[Pre-deployment Backup]
    B --> C[SSH к серверу]
    C --> D[Git pull]
    D --> E[Копирование .env.production]
    E --> F[Docker pull images]
    F --> G[Stop контейнеры]
    G --> H[Database migrations]
    H --> I[Start контейнеры]
    I --> J{Health Check?}
    J -->|OK| K[Cleanup старых images]
    J -->|FAIL| L[Автоматический Rollback]
    K --> M[✅ Deploy завершён]
    L --> N[❌ Rollback выполнен]
```

### Процесс деплоя подробно:

1. **Pre-deployment backup** — создание резервной копии текущей версии
2. **Pull latest code** — получение последних изменений из Git
3. **Set environment** — копирование `.env.production` → `.env`
4. **Pull Docker images** — загрузка новых образов из GHCR
5. **Stop old containers** — остановка текущих контейнеров
6. **Database migrations** — применение миграций через Alembic
7. **Start new containers** — запуск новых контейнеров
8. **Health check** — проверка работоспособности всех сервисов
9. **Cleanup** — удаление старых Docker образов

### Rollback (при ошибке)

Автоматически запускается `scripts/rollback.sh`:
- Откат к предыдущему Git commit
- Восстановление из pre-deploy backup
- Перезапуск контейнеров

---

## 🔐 Переменные GitHub Secrets

Добавьте в **Settings → Secrets and variables → Actions**:

### Обязательные для Production

| Secret | Описание | Пример |
|--------|----------|--------|
| `PRODUCTION_HOST` | IP/hostname production сервера | `192.168.1.100` или `api.example.com` |
| `PRODUCTION_SSH_PRIVATE_KEY` | SSH приватный ключ для деплоя | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DEPLOY_USER` | Пользователь для SSH | `deploy` |

### Опциональные для Staging

| Secret | Описание | Пример |
|--------|----------|--------|
| `STAGING_HOST` | IP/hostname staging сервера | `staging.example.com` |
| `STAGING_SSH_PRIVATE_KEY` | SSH ключ для staging | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

### Опциональные

| Secret | Описание | Пример |
|--------|----------|--------|
| `CODECOV_TOKEN` | Токен для Codecov (coverage отчёты) | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

---

## 🖥️ Подготовка Production сервера

### 1. Создание deploy пользователя

```bash
# На production сервере
sudo adduser deploy
sudo usermod -aG docker deploy
```

### 2. Настройка SSH ключа

```bash
# На локальной машине - генерация ключа
ssh-keygen -t ed25519 -f ~/.ssh/ffmpeg-api-deploy -C "deploy@ffmpeg-api"

# Скопировать публичный ключ на сервер
ssh-copy-id -i ~/.ssh/ffmpeg-api-deploy deploy@your-server.com

# Содержимое приватного ключа добавить в GitHub Secrets как PRODUCTION_SSH_PRIVATE_KEY
cat ~/.ssh/ffmpeg-api-deploy
```

### 3. Клонирование проекта на сервере

```bash
ssh deploy@your-server.com
sudo mkdir -p /opt/ffmpeg-api
sudo chown deploy:deploy /opt/ffmpeg-api
cd /opt/ffmpeg-api
git clone https://github.com/<your-repo>/ffmpeg-api.git .
```

### 4. Настройка .env.production

```bash
cp .env.production.example .env.production
nano .env.production  # Заполнить реальными значениями
```

### 5. Первый запуск

```bash
docker-compose -f docker-compose.prod.yml up -d
docker-compose exec api python scripts/init_db.py
docker-compose exec api python scripts/create_admin.py
```

---

## 📦 GitHub Container Registry

Docker образы автоматически публикуются в GHCR:

- `ghcr.io/<username>/ffmpeg-api/ffmpeg-api:latest`
- `ghcr.io/<username>/ffmpeg-api/ffmpeg-worker:latest`

Теги:
- `latest` — main branch
- `<branch-name>` — для dev веток
- `<sha>` — по commit hash
- `vX.Y.Z` — для releases

---

## 📝 Чеклист перед первым деплоем

- [ ] Заполнить `.env.production` реальными значениями
- [ ] Добавить `PRODUCTION_HOST` в GitHub Secrets
- [ ] Добавить `PRODUCTION_SSH_PRIVATE_KEY` в GitHub Secrets
- [ ] Создать deploy пользователя на сервере
- [ ] Настроить SSH доступ
- [ ] Клонировать репозиторий на сервер в `/opt/ffmpeg-api`
- [ ] Настроить SSL сертификаты (Let's Encrypt)
- [ ] Настроить DNS записи
- [ ] Выполнить первый ручной запуск для инициализации БД
- [ ] Push в main для запуска автоматического деплоя
