# Настройка VPS для FFmpeg API

Пошаговая инструкция по развёртыванию проекта на чистом VPS (Ubuntu 22.04).

---

## Шаг 1: Подключение к серверу

```bash
ssh root@<IP_ВАШЕГО_VPS>
```

---

## Шаг 2: Обновление системы

```bash
apt update && apt upgrade -y
apt install -y curl git htop mc
```

---

## Шаг 3: Установка Docker

```bash
# Установка Docker
curl -fsSL https://get.docker.com | sh

# Проверка
docker --version
docker compose version
```

---

## Шаг 4: Создание deploy пользователя (опционально, но рекомендуется)

```bash
# Создаём пользователя
adduser deploy
usermod -aG docker deploy
usermod -aG sudo deploy

# Настраиваем SSH для пользователя
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

---

## Шаг 5: Клонирование проекта

```bash
# Создаём директорию
mkdir -p /opt/ffmpeg-api
cd /opt/ffmpeg-api

# Клонируем репозиторий (замените на ваш URL)
git clone https://github.com/<ваш-username>/ffmpeg-api.git .

# Если используете deploy пользователя
chown -R deploy:deploy /opt/ffmpeg-api
```

---

## Шаг 6: Настройка переменных окружения

```bash
# Копируем пример
cp .env.production.example .env.production

# Редактируем (замените значения на свои!)
nano .env.production
```

**Обязательно измените:**
```env
# Безопасные пароли (сгенерируйте свои!)
POSTGRES_PASSWORD=<сильный_пароль_базы_данных>
MINIO_ROOT_PASSWORD=<сильный_пароль_minio>
JWT_SECRET=<случайная_строка_минимум_32_символа>
GRAFANA_ADMIN_PASSWORD=<пароль_для_grafana>

# Ваш домен или IP
API_BASE_URL=http://<IP_ВАШЕГО_VPS>:8000
CORS_ORIGINS=http://<IP_ВАШЕГО_VPS>
```

**Генерация случайных паролей:**
```bash
# JWT Secret (32+ символов)
openssl rand -base64 32

# Пароли БД
openssl rand -base64 16
```

---

## Шаг 7: Первый запуск

```bash
cd /opt/ffmpeg-api

# Копируем production env
cp .env.production .env

# Запускаем все сервисы (первый раз займёт 10-15 минут на сборку)
docker compose -f docker-compose.prod.yml up -d --build

# Проверяем статус
docker compose -f docker-compose.prod.yml ps
```

---

## Шаг 8: Инициализация базы данных

```bash
# Ждём пока PostgreSQL запустится (30-60 секунд)
sleep 30

# Применяем миграции
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Создаём admin пользователя
docker compose -f docker-compose.prod.yml exec api python scripts/init_db.py
```

---

## Шаг 9: Проверка работы

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Или с внешнего IP
curl http://<IP_ВАШЕГО_VPS>:8000/api/v1/health
```

**Ожидаемый ответ:**
```json
{"status": "healthy", "version": "1.0.0"}
```

---

## Шаг 10: Настройка файрвола

```bash
# Разрешаем нужные порты
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS

# Включаем файрвол
ufw enable

# Проверяем
ufw status
```

---

## Шаг 11: Настройка GitHub Actions (автодеплой)

### На локальной машине создайте SSH ключ:

```bash
# Генерация ключа
ssh-keygen -t ed25519 -f ~/.ssh/ffmpeg-api-deploy -C "github-actions-deploy"

# Показать публичный ключ (добавить на сервер)
cat ~/.ssh/ffmpeg-api-deploy.pub

# Показать приватный ключ (добавить в GitHub Secrets)
cat ~/.ssh/ffmpeg-api-deploy
```

### На VPS сервере добавьте публичный ключ:

```bash
# Под пользователем deploy (или root)
echo "ssh-ed25519 AAAA... github-actions-deploy" >> ~/.ssh/authorized_keys
```

### В GitHub репозитории добавьте Secrets:

`Settings → Secrets and variables → Actions → New repository secret`

| Secret | Значение |
|--------|----------|
| `PRODUCTION_HOST` | IP вашего VPS |
| `PRODUCTION_SSH_PRIVATE_KEY` | Содержимое `~/.ssh/ffmpeg-api-deploy` |
| `DEPLOY_USER` | `deploy` (или `root`) |

---

## Шаг 12: Тестовый деплой

После настройки Secrets, сделайте push в main:

```bash
git add .
git commit -m "Test deploy"
git push origin main
```

GitHub Actions автоматически:
1. Прогонит тесты
2. Соберёт Docker образы
3. Задеплоит на ваш VPS

---

## Полезные команды

```bash
# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker

# Перезапуск сервисов
docker compose -f docker-compose.prod.yml restart

# Остановка
docker compose -f docker-compose.prod.yml down

# Обновление вручную
cd /opt/ffmpeg-api
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Доступные сервисы

После успешного запуска:

| Сервис | URL | Логин |
|--------|-----|-------|
| **API** | http://IP:8000/docs | - |
| **Grafana** | http://IP:3000 | admin / (из .env) |
| **Flower** | http://IP:5555 | admin / admin |
| **MinIO** | http://IP:9001 | (из .env) |

---

## Troubleshooting

### Контейнеры не запускаются
```bash
docker compose -f docker-compose.prod.yml logs
```

### Нет места на диске
```bash
docker system prune -a
```

### База данных не подключается
```bash
docker compose -f docker-compose.prod.yml exec postgres pg_isready
```
