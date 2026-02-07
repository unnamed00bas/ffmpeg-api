# Stage 1.5 - База данных

## Обзор

Документация для реализации базы данных проекта FFmpeg API. Включает описание моделей, репозиториев и инструментов миграции.

## Структура

```
app/database/
├── models/              # SQLAlchemy модели
│   ├── base.py        # Базовая модель
│   ├── user.py        # Модель пользователя
│   ├── task.py        # Модель задачи
│   ├── file.py        # Модель файла
│   ├── operation_log.py # Модель лога операций
│   ├── metrics.py     # Модель метрик
│   └── __init__.py   # Экспорт моделей
├── repositories/         # Репозитории
│   ├── base.py        # Базовый репозиторий
│   ├── user_repository.py # Репозиторий пользователей
│   ├── task_repository.py # Репозиторий задач
│   ├── file_repository.py # Репозиторий файлов
│   └── __init__.py   # Экспорт репозиториев
├── connection.py        # Управление соединением с БД
└── __init__.py        # Экспорт модуля

alembic/
├── env.py            # Конфигурация Alembic
├── script.py.mako    # Шабон миграций
└── versions/         # Файлы миграций

scripts/
└── init_db.py        # Скрипт инициализации БД

tests/database/
├── test_models.py    # Тесты моделей
└── test_repositories.py # Тесты репозиториев
```

## Модели данных

### BaseModel (`app/database/models/base.py`)

Базовая модель для всех таблиц базы данных.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время последнего обновления

**Функции:**
- Автоматическое заполнение `created_at` и `updated_at`
- Поддержка SQLAlchemy 2.0 async/await

### User (`app/database/models/user.py`)

Модель пользователя для аутентификации и авторизации.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `username` (String(50), unique, indexed): Имя пользователя
- `email` (String(255), unique, indexed): Email адрес
- `hashed_password` (String(255)): Хешированный пароль (BCrypt)
- `api_key` (String(64), unique, nullable, indexed): API ключ для аутентификации
- `settings` (JSON): Настройки пользователя
- `is_admin` (Boolean): Флаг администратора (default: False)
- `is_active` (Boolean): Флаг активности (default: True)
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время обновления

**Индексы:**
- `username`, `email`, `api_key`, `is_active`

**Отношения:**
- `tasks` (1:N): Связь с задачами
- `files` (1:N): Связь с файлами

### Task (`app/database/models/task.py`)

Модель задачи для обработки видео.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `user_id` (Integer, FK): ID пользователя
- `type` (Enum): Тип задачи (join, audio_overlay, text_overlay, subtitles, video_overlay, combined)
- `status` (Enum): Статус (pending, processing, completed, failed, cancelled)
- `input_files` (JSON): Список входных файлов
- `output_files` (JSON): Список выходных файлов
- `config` (JSON, nullable): Конфигурация задачи
- `error_message` (String, nullable): Сообщение об ошибке
- `progress` (Float): Прогресс выполнения (0.0-100.0)
- `result` (JSON, nullable): Результат выполнения
- `retry_count` (Integer): Количество повторных попыток
- `completed_at` (DateTime, nullable): Время завершения
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время обновления

**Enum типы:**
- `TaskType`: JOIN, AUDIO_OVERLAY, TEXT_OVERLAY, SUBTITLES, VIDEO_OVERLAY, COMBINED
- `TaskStatus`: PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED

**Индексы:**
- `(user_id, status)`, `status`, `created_at`, `type`

**Отношения:**
- `user` (N:1): Связь с пользователем
- `operation_logs` (1:N): Связь с логами операций

### File (`app/database/models/file.py`)

Модель файла для хранения метаданных.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `user_id` (Integer, FK): ID пользователя
- `filename` (String): Имя файла в хранилище
- `original_filename` (String): Оригинальное имя файла
- `size` (Integer): Размер файла в байтах
- `content_type` (String): MIME тип
- `storage_path` (String): Путь в хранилище
- `metadata` (JSON, nullable): Метаданные (длительность, разрешение, кодек и т.д.)
- `is_deleted` (Boolean): Флаг мягкого удаления
- `deleted_at` (DateTime, nullable): Время удаления
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время обновления

**Индексы:**
- `user_id`, `is_deleted`, `created_at`, `(user_id, is_deleted)`

**Отношения:**
- `user` (N:1): Связь с пользователем

### OperationLog (`app/database/models/operation_log.py`)

Модель лога операций для отслеживания выполнения задач.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `task_id` (Integer, FK): ID задачи
- `operation_type` (String): Тип операции
- `duration` (Float): Длительность в секундах
- `success` (Boolean): Успешность операции
- `error_details` (JSON, nullable): Детали ошибки
- `timestamp` (DateTime): Время операции
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время обновления

**Индексы:**
- `task_id`, `operation_type`, `timestamp`, `(task_id, timestamp)`

**Отношения:**
- `task` (N:1): Связь с задачей

### Metrics (`app/database/models/metrics.py`)

Модель метрик приложения.

**Поля:**
- `id` (Integer, PK): Первичный ключ
- `metric_name` (String): Название метрики
- `metric_value` (Float): Значение метрики
- `tags` (JSON, nullable): Теги метрики
- `timestamp` (DateTime): Время метрики
- `created_at` (DateTime): Время создания
- `updated_at` (DateTime): Время обновления

**Индексы:**
- `(metric_name, timestamp)`, `metric_name`, `timestamp`

## Репозитории

### BaseRepository (`app/database/repositories/base.py`)

Базовый класс репозитория с CRUD операциями.

**Методы:**
- `create(**kwargs) -> T`: Создать новую запись
- `get_by_id(id) -> Optional[T]`: Получить запись по ID
- `get_all(offset, limit, **filters) -> List[T]`: Получить все записи с фильтрацией и пагинацией
- `update(obj, **kwargs) -> T`: Обновить запись
- `update_by_id(id, **kwargs) -> Optional[T]`: Обновить запись по ID
- `delete(obj) -> bool`: Удалить запись
- `delete_by_id(id) -> bool`: Удалить запись по ID
- `count(**filters) -> int`: Подсчитать записи
- `exists(id) -> bool`: Проверить существование записи

### UserRepository (`app/database/repositories/user_repository.py`)

Репозиторий для работы с пользователями.

**Методы:**
- `create(username, email, password, **kwargs) -> User`: Создать пользователя с хешированием пароля
- `get_by_id(id) -> Optional[User]`: Получить пользователя по ID
- `get_by_email(email) -> Optional[User]`: Получить пользователя по email
- `get_by_username(username) -> Optional[User]`: Получить пользователя по имени
- `get_by_api_key(api_key) -> Optional[User]`: Получить пользователя по API ключу
- `get_users(offset, limit, active_only) -> List[User]`: Получить список пользователей
- `authenticate(email, password) -> Optional[User]`: Аутентифицировать пользователя
- `generate_api_key(user_id) -> str`: Сгенерировать API ключ
- `revoke_api_key(user_id) -> bool`: Отозвать API ключ
- `change_password(user_id, old_password, new_password) -> bool`: Изменить пароль
- `activate_user(user_id) -> bool`: Активировать пользователя
- `deactivate_user(user_id) -> bool`: Деактивировать пользователя

**Хеширование паролей:**
- Используется BCrypt через `passlib`
- Автоматическое хеширование при создании пользователя
- Проверка паролей при аутентификации

### TaskRepository (`app/database/repositories/task_repository.py`)

Репозиторий для работы с задачами.

**Методы:**
- `create(user_id, task_type, config, **kwargs) -> Task`: Создать задачу
- `get_by_id(id) -> Optional[Task]`: Получить задачу по ID
- `get_by_user(user_id, offset, limit, filters) -> List[Task]`: Получить задачи пользователя
- `get_by_status(status) -> List[Task]`: Получить задачи по статусу
- `get_by_type(task_type) -> List[Task]`: Получить задачи по типу
- `get_by_user_and_status(user_id, status, offset, limit) -> List[Task]`: Получить задачи пользователя по статусу
- `update_status(task_id, status, error_message) -> Optional[Task]`: Обновить статус задачи
- `update_progress(task_id, progress) -> Optional[Task]`: Обновить прогресс задачи
- `update_result(task_id, result) -> Optional[Task]`: Обновить результат задачи
- `get_pending_tasks(limit) -> List[Task]`: Получить ожидающие задачи
- `get_tasks_statistics(user_id) -> Dict`: Получить статистику задач
- `increment_retry_count(task_id) -> Optional[Task]`: Увеличить счетчик повторных попыток
- `get_user_active_tasks_count(user_id) -> int`: Получить количество активных задач пользователя
- `cancel_task(task_id) -> Optional[Task]`: Отменить задачу
- `get_completed_tasks_in_period(user_id, start_date, end_date) -> List[Task]`: Получить завершенные задачи за период

### FileRepository (`app/database/repositories/file_repository.py`)

Репозиторий для работы с файлами.

**Методы:**
- `create(user_id, filename, original_filename, size, content_type, storage_path, metadata, **kwargs) -> File`: Создать файл
- `get_by_id(id) -> Optional[File]`: Получить файл по ID
- `get_by_user(user_id, offset, limit, include_deleted) -> List[File]`: Получить файлы пользователя
- `get_by_storage_path(storage_path) -> Optional[File]`: Получить файл по пути в хранилище
- `get_by_content_type(user_id, content_type, offset, limit) -> List[File]`: Получить файлы по MIME типу
- `mark_as_deleted(file_id) -> bool`: Мягкое удаление файла
- `mark_as_deleted_by_storage_path(storage_path) -> bool`: Мягкое удаление по пути
- `restore(file_id) -> bool`: Восстановить файл
- `get_user_storage_usage(user_id) -> int`: Получить использование хранилища пользователя
- `get_user_file_count(user_id, include_deleted) -> int`: Получить количество файлов пользователя
- `get_files_by_size_range(user_id, min_size, max_size, offset, limit) -> List[File]`: Получить файлы по размеру
- `get_files_by_date_range(user_id, start_date, end_date, offset, limit) -> List[File]`: Получить файлы за период
- `get_large_files(user_id, min_size_mb, limit) -> List[File]`: Получить большие файлы
- `get_recent_files(user_id, days, limit) -> List[File]`: Получить последние файлы
- `delete_permanently(file_id) -> bool`: Перманентное удаление файла
- `get_files_statistics(user_id) -> Dict`: Получить статистику файлов
- `update_metadata(file_id, metadata) -> Optional[File]`: Обновить метаданные файла

## Миграции (Alembic)

### Конфигурация

**`alembic.ini`:**
- Настройки подключения к базе данных
- Путь к миграциям
- Шаблоны именования миграций

**`alembic/env.py`:**
- Конфигурация для async движка
- Импорт всех моделей для autogenerate
- Поддержка онлайн и офлайн режимов

**`alembic/script.py.mako`:**
- Шабон для генерации миграций

### Команды

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1

# Показать историю миграций
alembic history

# Показать текущую версию
alembic current
```

## Инициализация базы данных

### Скрипт `scripts/init_db.py`

Скрипт для первичной инициализации базы данных.

**Функционал:**
1. Создание всех таблиц базы данных
2. Создание администратора по умолчанию:
   - Email: `admin@example.com`
   - Пароль: `admin123`
   - API ключ: генерируется автоматически
3. Опционально: создание тестовых данных

**Запуск:**

```bash
python scripts/init_db.py
```

**Примечание:**
- В production используйте Alembic миграции вместо прямого создания таблиц
- Скрипт автоматически генерирует API ключ для администратора
- Выводит учетные данные администратора в консоль

## Тестирование

### Запуск тестов

```bash
# Запустить все тесты
pytest

# Запустить тесты с покрытием
pytest --cov=app/database

# Запустить конкретный файл тестов
pytest tests/database/test_models.py
pytest tests/database/test_repositories.py

# Запустить с выводом
pytest -v
```

### Тестовые файлы

**`tests/database/test_models.py`:**
- Тесты создания моделей
- Тесты валидации полей
- Тесты значений по умолчанию
- Тесты отношений между моделями
- Тесты строковых представлений (`__repr__`)

**`tests/database/test_repositories.py`:**
- Тесты CRUD операций
- Тесты хеширования паролей
- Тесты аутентификации
- Тесты работы с API ключами
- Тесты обновления статусов и прогресса
- Тесты фильтрации и пагинации
- Тесты статистики

## Использование

### Примеры кода

#### Создание пользователя

```python
from app.database import get_db
from app.database.repositories import UserRepository

async def create_user():
    async for session in get_db():
        repo = UserRepository(session)
        user = await repo.create(
            username="john_doe",
            email="john@example.com",
            password="secure_password"
        )
        print(f"User created: {user.username}")
        break
```

#### Создание задачи

```python
from app.database import get_db
from app.database.repositories import TaskRepository
from app.database.models import TaskType

async def create_task():
    async for session in get_db():
        repo = TaskRepository(session)
        task = await repo.create(
            user_id=1,
            task_type=TaskType.JOIN,
            config={"resolution": "1080p"}
        )
        print(f"Task created: {task.id}")
        break
```

#### Обновление прогресса задачи

```python
from app.database import get_db
from app.database.repositories import TaskRepository

async def update_task_progress():
    async for session in get_db():
        repo = TaskRepository(session)
        task = await repo.update_progress(task_id=1, progress=50.0)
        print(f"Task progress: {task.progress}%")
        break
```

#### Получение статистики пользователя

```python
from app.database import get_db
from app.database.repositories import UserRepository, FileRepository

async def get_user_stats():
    async for session in get_db():
        user_repo = UserRepository(session)
        file_repo = FileRepository(session)
        
        storage_usage = await file_repo.get_user_storage_usage(user_id=1)
        file_count = await file_repo.get_user_file_count(user_id=1)
        
        print(f"Storage usage: {storage_usage} bytes")
        print(f"File count: {file_count}")
        break
```

## Настройки

### Переменные окружения

В `.env` файле:

```bash
# Database
POSTGRES_DB=ffmpeg_api
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DATABASE_URL=postgresql+asyncpg://postgres_user:postgres_password@localhost:5432/ffmpeg_api
```

### Пул соединений

Настройки в `app/database/connection.py`:

```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,        # Логирование SQL запросов
    pool_size=10,              # Размер пула
    max_overflow=20,           # Максимальное количество дополнительных соединений
    pool_pre_ping=True          # Проверка соединения перед использованием
)
```

## Рекомендации

### Производительность

1. **Индексы:** Все важные поля проиндексированы для быстрого поиска
2. **Пагинация:** Используйте параметры `offset` и `limit` для больших выборок
3. **Связи:** SQLAlchemy 2.0 использует lazy loading по умолчанию
4. **JSON поля:** Используйте JSON поля только для редко изменяемых данных

### Безопасность

1. **Пароли:** Все пароли хешируются через BCrypt
2. **SQL Injection:** SQLAlchemy использует параметризованные запросы
3. **API ключи:** Генерируются криптографически безопасным способом
4. **Мягкое удаление:** Файлы не удаляются физически из БД

### Мониторинг

1. **Логирование:** Включите `DEBUG=True` для детального логирования SQL
2. **Метрики:** Используйте модель `Metrics` для сбора статистики
3. **Логи операций:** `OperationLog` для отслеживания длительности операций

## Следующие шаги

1. **API Эндпоинты:** Создать API эндпоинты для работы с пользователями, задачами и файлами
2. **Аутентификация:** Реализовать JWT токены и middleware для защиты API
3. **Обработка файлов:** Интеграция с MinIO для хранения файлов
4. **Обработка видео:** Реализовать FFmpeg интеграцию для обработки задач
5. **Celery:** Настроить фоновые задачи для асинхронной обработки

## Устранение проблем

### Ошибка: "relation already exists"

Это может произойти, если вы запускаете миграции несколько раз. Решение:

```bash
# Сбросить миграцию
alembic downgrade base

# Или пересоздать таблицы (только для разработки!)
python scripts/init_db.py
```

### Ошибка: "connection refused"

Убедитесь, что PostgreSQL запущен и доступен:

```bash
# Проверьте переменные окружения
echo $DATABASE_URL

# Проверьте соединение
psql $DATABASE_URL
```

### Ошибка: "no such table: users"

Убедитесь, что миграции применены:

```bash
alembic upgrade head
```

## Дополнительные ресурсы

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
