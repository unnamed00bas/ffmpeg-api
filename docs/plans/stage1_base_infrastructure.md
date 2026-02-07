# Этап 1: Базовая инфраструктура (Недели 1-2)

## Обзор этапа

Этап закладывает фундамент проекта: настраивает Docker окружение, базу данных PostgreSQL, систему аутентификации и мониторинг. Все компоненты должны быть полностью функциональными и протестированными.

---

## Подзадача 1.4: Docker окружение и мониторинг

### Задачи реализации

**Настройка Prometheus:**
- Создать [docker/prometheus.yml](docker/prometheus.yml) для сбора метрик:
  - Scrape конфигурация для FastAPI API (порт 8000)
  - Scrape конфигурация для Celery Worker (метрики Flower)
  - Scrape конфигурация для PostgreSQL (exporter)
  - Scrape конфигурация для Redis (exporter)
  - Retention policy: 30 дней данных

**Создание Grafana дашбордов:**
- [docker/grafana/dashboards/api_performance.json](docker/grafana/dashboards/api_performance.json):
  - Requests per second (по endpoint)
  - Response time (p50, p95, p99)
  - Error rate (по кодам ответа)
  - Active connections
- [docker/grafana/dashboards/system_resources.json](docker/grafana/dashboards/system_resources.json):
  - CPU utilization (по контейнерам)
  - RAM usage (по контейнерам)
  - Disk I/O
  - Network traffic
- [docker/grafana/dashboards/celery_tasks.json](docker/grafana/dashboards/celery_tasks.json):
  - Queue size (pending, processing, failed)
  - Task duration (среднее, p95)
  - Success/failure rate
  - Worker utilization

**Настройка datasource:**
- [docker/grafana/datasources/prometheus.yml](docker/grafana/datasources/prometheus.yml):
  - Prometheus URL: http://prometheus:9090
  - Автообновление: 5 секунд

### Тестирование подзадачи 1.4

**Smoke тесты:**
- Все контейнеры запускаются без ошибок: `docker-compose up -d`
- Health checks всех сервисов проходят: проверка статусов через `docker-compose ps`

**Health check тесты:**
- PostgreSQL: `pg_isready` возвращает OK
- Redis: `redis-cli ping` возвращает PONG
- MinIO: `/minio/health/live` возвращает 200
- API: `/api/v1/health` возвращает 200
- Celery Worker: активен и готов к обработке задач

**Интеграционные тесты:**
- API успешно подключается к PostgreSQL: проверка connection pool
- API успешно подключается к Redis: проверка команд SET/GET
- API успешно подключается к MinIO: проверка создания бакета
- Celery Worker подключается к Redis broker: проверка через Flower

**Мониторинг тесты:**
- Prometheus собирает метрики с API: проверка `/api/v1/metrics`
- Prometheus собирает метрики с других сервисов
- Grafana отображает все дашборды
- Графики обновляются в реальном времени
- Метрики корректны (числовые значения, типы данных)

**Сетевое взаимодействие:**
- API может обращаться к PostgreSQL: проверка ping
- API может обращаться к Redis: проверка ping
- API может обращаться к MinIO: проверка API
- Worker может обращаться к БД и Redis
- Grafana может обращаться к Prometheus

---

## Подзадача 1.5: База данных

### Задачи реализации

**SQLAlchemy модели в [app/database/models/](app/database/models/):**

**Base model** - [app/database/models/base.py](app/database/models/base.py):
```python
class BaseModel(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(onupdate=datetime.utcnow)
```

**User model** - [app/database/models/user.py](app/database/models/user.py):
- id (int, PK)
- username (str, unique, indexed)
- email (str, unique, indexed)
- hashed_password (str)
- api_key (str, unique, nullable, indexed)
- settings (JSON, nullable)
- is_admin (bool, default=False)
- is_active (bool, default=True)
- created_at (datetime)
- updated_at (datetime)

**Task model** - [app/database/models/task.py](app/database/models/task.py):
- id (int, PK)
- user_id (int, FK to users, indexed)
- type (Enum: join, audio_overlay, text_overlay, subtitles, video_overlay, combined)
- status (Enum: pending, processing, completed, failed, cancelled)
- input_files (JSON list of file IDs)
- output_files (JSON list of file IDs)
- config (JSON, nullable)
- error_message (str, nullable)
- progress (float, 0.0-100.0)
- result (JSON, nullable)
- retry_count (int, default=0)
- created_at (datetime)
- updated_at (datetime)
- completed_at (datetime, nullable)
- Indexes: (user_id, status), (status), (created_at)

**File model** - [app/database/models/file.py](app/database/models/file.py):
- id (int, PK)
- user_id (int, FK to users, indexed)
- filename (str, storage path)
- original_filename (str)
- size (int)
- content_type (str)
- storage_path (str)
- metadata (JSON: duration, resolution, codec, etc.)
- is_deleted (bool, default=False)
- deleted_at (datetime, nullable)
- created_at (datetime)
- Indexes: (user_id), (is_deleted), (created_at)

**OperationLog model** - [app/database/models/operation_log.py](app/database/models/operation_log.py):
- id (int, PK)
- task_id (int, FK to tasks, indexed)
- operation_type (str)
- duration (float, seconds)
- success (bool)
- error_details (JSON, nullable)
- timestamp (datetime)
- Indexes: (task_id), (operation_type), (timestamp)

**Metrics model** - [app/database/models/metrics.py](app/database/models/metrics.py):
- id (int, PK)
- metric_name (str, indexed)
- metric_value (float)
- tags (JSON, nullable)
- timestamp (datetime)
- Indexes: (metric_name, timestamp)

**Базовые репозитории в [app/database/repositories/](app/database/repositories/):**

**Base repository** - [app/database/repositories/base.py](app/database/repositories/base.py):
```python
class BaseRepository(Generic[T]):
    async def create(self, **kwargs) -> T
    async def get_by_id(self, id: int) -> Optional[T]
    async def get_all(self, offset: int = 0, limit: int = 100) -> List[T]
    async def update(self, obj: T, **kwargs) -> T
    async def delete(self, obj: T) -> bool
```

**UserRepository** - [app/database/repositories/user_repository.py](app/database/repositories/user_repository.py):
- create(username, email, password) -> User
- get_by_id(id) -> Optional[User]
- get_by_email(email) -> Optional[User]
- get_by_username(username) -> Optional[User]
- get_by_api_key(api_key) -> Optional[User]
- update(user, **kwargs) -> User
- get_users(offset, limit) -> List[User]

**TaskRepository** - [app/database/repositories/task_repository.py](app/database/repositories/task_repository.py):
- create(user_id, type, config) -> Task
- get_by_id(id) -> Optional[Task]
- get_by_user(user_id, offset, limit, filters) -> List[Task]
- get_by_status(status) -> List[Task]
- update_status(task_id, status, error=None) -> Task
- update_progress(task_id, progress) -> Task
- update_result(task_id, result) -> Task
- get_pending_tasks(limit) -> List[Task]
- get_tasks_statistics(user_id) -> Dict

**FileRepository** - [app/database/repositories/file_repository.py](app/database/repositories/file_repository.py):
- create(user_id, filename, original_filename, size, content_type, storage_path, metadata) -> File
- get_by_id(id) -> Optional[File]
- get_by_user(user_id, offset, limit, include_deleted=False) -> List[File]
- update(file, **kwargs) -> File
- mark_as_deleted(file_id) -> bool
- get_user_storage_usage(user_id) -> int

**Настройка Alembic:**
- Создать [alembic.ini](alembic.ini) в корне проекта
- Создать [alembic/env.py](alembic/env.py) с настройкой метаданных
- Создать [alembic/versions/](alembic/versions/) для миграций
- Инициализация: `alembic init alembic`
- Первая миграция: `alembic revision --autogenerate -m "Initial migration"`
- Применение миграций: `alembic upgrade head`

**Инициализация базы данных:**
- Создать [scripts/init_db.py](scripts/init_db.py):
  - Создание таблиц через SQLAlchemy
  - Создание начального admin пользователя
  - Создание тестовых данных (опционально)

### Тестирование подзадачи 1.5

**Unit тесты моделей:**
- Проверка всех полей моделей (типы, значения по умолчанию)
- Проверка отношений (Foreign Keys, relationships)
- Проверка валидации данных
- Проверка индексов

**Unit тесты репозиториев:**

*UserRepository тесты:*
- create() создает пользователя с хешированным паролем
- get_by_id() возвращает пользователя или None
- get_by_email() находит пользователя по email
- get_by_username() находит пользователя по username
- get_by_api_key() находит пользователя по api_key
- update() обновляет поля пользователя
- get_users() возвращает пагинированный список

*TaskRepository тесты:*
- create() создает задачу с корректными полями
- get_by_id() возвращает задачу или None
- get_by_user() возвращает задачи пользователя с пагинацией
- get_by_user() поддерживает фильтры (status, type, date range)
- update_status() обновляет статус и error_message
- update_progress() обновляет прогресс (0.0-100.0)
- update_result() сохраняет результат задачи
- get_pending_tasks() возвращает задачи со статусом pending
- get_tasks_statistics() возвращает корректную статистику

*FileRepository тесты:*
- create() создает файл с корректными метаданными
- get_by_id() возвращает файл или None
- get_by_user() возвращает файлы пользователя с пагинацией
- get_by_user() учитывает include_deleted флаг
- update() обновляет поля файла
- mark_as_deleted() помечает файл как удаленный
- get_user_storage_usage() считает корректный размер

**Тесты миграций:**
- Применение миграции: `alembic upgrade head` проходит без ошибок
- Откат миграции: `alembic downgrade -1` проходит без ошибок
- Применение нескольких миграций подряд
- Проверка создания всех таблиц
- Проверка создания всех индексов
- Проверка создания Foreign Keys

**Интеграционные тесты:**
- Подключение к реальной PostgreSQL из контейнера
- Транзакции: rollback работает корректно
- Connection pool: работает корректно при нагрузке
- Concurrent запросы: несколько запросов выполняются параллельно

**Performance тесты:**
- Время выполнения базовых CRUD операций < 50ms
- Время выполнения сложных запросов с JOIN < 100ms
- Connection pool оптимально настроен

---

## Подзадача 1.6: Аутентификация

### Задачи реализации

**JWT сервис в [app/auth/jwt.py](app/auth/jwt.py):**

```python
class JWTService:
    def create_access_token(user_id: int, expires_delta: timedelta) -> str
    def create_refresh_token(user_id: int, expires_delta: timedelta) -> str
    def verify_token(token: str) -> TokenPayload
    def decode_token(token: str) -> Dict[str, Any]
```

**Password hashing в [app/auth/security.py](app/auth/security.py):**

```python
class SecurityService:
    def hash_password(password: str) -> str
    def verify_password(plain_password: str, hashed_password: str) -> bool
    def generate_api_key() -> str
```

**Dependencies в [app/auth/dependencies.py](app/auth/dependencies.py):**

```python
def get_current_user(token: str = Depends(oauth2_scheme)) -> User
def get_current_active_user(current_user: User = Depends(get_current_user)) -> User
def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User
def require_api_key(api_key: str = Header(...)) -> User
```

**Auth endpoints в [app/api/v1/auth.py](app/api/v1/auth.py):**

- POST /api/v1/auth/register:
  - Body: {username, email, password}
  - Response: {id, username, email, created_at}
  - Validation: email format, password strength, unique email/username

- POST /api/v1/auth/login:
  - Body: {email_or_username, password}
  - Response: {access_token, refresh_token, token_type, expires_in}
  - OAuth2PasswordBearer scheme

- POST /api/v1/auth/refresh:
  - Body: {refresh_token}
  - Response: {access_token, token_type, expires_in}
  - Валидация refresh токена

- GET /api/v1/auth/me:
  - Headers: Authorization: Bearer {access_token}
  - Response: {id, username, email, settings, created_at}
  - Требует авторизации

**Обновление [app/api/v1/router.py](app/api/v1/router.py):**
- Добавить auth_router с префиксом /api/v1/auth

### Тестирование подзадачи 1.6

**Unit тесты JWT сервиса:**
- create_access_token() создает валидный JWT токен
- create_refresh_token() создает валидный refresh токен
- verify_token() валидирует корректный токен
- verify_token() выбрасывает исключение для просроченного токена
- verify_token() выбрасывает исключение для некорректного токена
- verify_token() возвращает корректный TokenPayload с user_id, exp, iat
- decode_token() декодирует токен в словарь

**Unit тесты password hashing:**
- hash_password() создает разные хеши для одного пароля (salt)
- hash_password() создает детерминированный хеш с заданным salt (опционально)
- verify_password() возвращает True для правильного пароля
- verify_password() возвращает False для неправильного пароля
- verify_password() корректно работает с bcrypt
- generate_api_key() генерирует уникальный ключ
- generate_api_key() генерирует ключ безопасной длины (32+ символов)

**Unit тесты зависимостей:**
- get_current_user() возвращает User из валидного токена
- get_current_user() выбрасывает HTTPException для невалидного токена
- get_current_active_user() возвращает активного пользователя
- get_current_active_user() выбрасывает HTTPException для неактивного пользователя
- get_current_admin_user() возвращает admin пользователя
- get_current_admin_user() выбрасывает HTTPException для non-admin пользователя
- require_api_key() возвращает User из валидного API ключа
- require_api_key() выбрасывает HTTPException для невалидного API ключа

**Интеграционные тесты endpoints:**

*POST /api/v1/auth/register:*
- Успешная регистрация возвращает 201 и данные пользователя
- Регистрация с существующим email возвращает 400
- Регистрация с существующим username возвращает 400
- Регистрация с некорректным email возвращает 422
- Регистрация со слабым паролем возвращает 422
- Пароль хешируется перед сохранением в БД

*POST /api/v1/auth/login:*
- Успешный логин возвращает 200 и access + refresh токены
- Логин с неверным email возвращает 401
- Логин с неверным паролем возвращает 401
- Логин по username также работает
- Access токен истекает через заданное время
- Refresh токен имеет длительный срок жизни

*POST /api/v1/auth/refresh:*
- Успешный refresh возвращает новый access токен
- Refresh с истекшим токеном возвращает 401
- Refresh с некорректным токеном возвращает 401
- Новый токен имеет корректный срок жизни

*GET /api/v1/auth/me:*
- Успешный запрос возвращает 200 и данные пользователя
- Запрос без токена возвращает 401
- Запрос с истекшим токеном возвращает 401
- Запрос с некорректным токеном возвращает 401
- Ответ не содержит sensitive данные (пароль, api_key)

**Тесты безопасности:**
- Brute force атаки предотвращаются (rate limiting)
- JWT секрет не уте в логах
- API ключи не выводятся в ответах
- Password не возвращается ни в одном endpoint
- Refresh токен может использоваться только один раз (опционально)
- Токены проверяются на подпись

---

## Критерии завершения Этапа 1

**Функциональные требования:**
- Все контейнеры в Docker запускаются и работают без ошибок
- PostgreSQL база данных развернута, миграции применены
- Все SQLAlchemy модели созданы и работают
- Все репозитории реализуют CRUD операции
- Система аутентификации полностью функциональна
- Все auth endpoints работают корректно
- Prometheus собирает метрики со всех сервисов
- Grafana отображает все дашборды

**Требования к тестированию:**
- Все unit тесты для моделей проходят
- Все unit тесты для репозиториев проходят
- Все unit тесты для аутентификации проходят
- Все интеграционные тесты проходят
- Coverage > 70% для кода этапа 1

**Документация:**
- Модели документированы (docstrings)
- Репозитории документированы (docstrings)
- Auth endpoints документированы в OpenAPI (/docs)
- Prometheus конфигурация документирована
- Grafana дашборды имеют описания

**Производительность:**
- Health checks всех сервисов < 1 сек
- API response time < 100ms
- DB queries < 50ms
- Prometheus scrape time < 5s
