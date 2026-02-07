# Аутентификация - Подзадача 1.6

## Обзор

Документация модуля аутентификации для FFmpeg API Service.

## Структура модуля

```
app/
├── auth/
│   ├── __init__.py
│   ├── jwt.py              # JWT сервис для создания и валидации токенов
│   ├── security.py         # Сервис для хеширования паролей и генерации API ключей
│   └── dependencies.py     # FastAPI зависимости для аутентификации
├── api/v1/
│   └── auth.py             # API endpoints для аутентификации
└── database/
    ├── models/
    │   └── user.py         # Модель пользователя
    └── repositories/
        └── user_repository.py  # Репозиторий для работы с пользователями
```

## Конфигурация

Настройки аутентификации находятся в `app/config.py`:

```python
JWT_SECRET: str = "change-this-secret-key-minimum-32-characters"
JWT_ALGORITHM: str = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
```

**Важно:** Измените `JWT_SECRET` в production окружении!

## Компоненты

### 1. JWT Service (`app/auth/jwt.py`)

Сервис для создания и валидации JWT токенов.

**Основные методы:**

- `create_access_token(user_id, expires_delta)` - создает access токен (30 минут по умолчанию)
- `create_refresh_token(user_id, expires_delta)` - создает refresh токен (7 дней по умолчанию)
- `verify_token(token)` - валидирует токен и возвращает TokenPayload
- `decode_token(token)` - декодирует токен
- `get_user_id_from_token(token)` - извлекает user_id из токена
- `is_refresh_token(token)` - проверяет, является ли токен refresh токеном
- `is_access_token(token)` - проверяет, является ли токен access токеном

**Пример использования:**

```python
from app.auth.jwt import JWTService

jwt_service = JWTService(
    secret_key=settings.JWT_SECRET,
    algorithm=settings.JWT_ALGORITHM
)

# Создание токена
access_token = jwt_service.create_access_token(user_id=1)
refresh_token = jwt_service.create_refresh_token(user_id=1)

# Валидация токена
payload = jwt_service.verify_token(access_token)
print(f"User ID: {payload.user_id}")
```

### 2. Security Service (`app/auth/security.py`)

Сервис для хеширования паролей и генерации API ключей.

**Основные методы:**

- `hash_password(password)` - хеширует пароль с помощью bcrypt
- `verify_password(plain_password, hashed_password)` - проверяет пароль
- `generate_api_key()` - генерирует безопасный API ключ (32+ символов)
- `validate_password_strength(password)` - валидирует сложность пароля
- `is_strong_password(password)` - проверяет, является ли пароль сильным
- `validate_email(email)` - валидирует формат email
- `generate_reset_token()` - генерирует токен для сброса пароля
- `generate_verification_token()` - генерирует токен для подтверждения email

**Требования к паролю:**

- Минимум 8 символов
- Как минимум одна заглавная буква
- Как минимум одна строчная буква
- Как минимум одна цифра
- Не должен быть в списке общих слабых паролей

**Пример использования:**

```python
from app.auth.security import SecurityService

security_service = SecurityService()

# Хеширование пароля
hashed_password = security_service.hash_password("SecurePass123")

# Проверка пароля
is_valid = security_service.verify_password("SecurePass123", hashed_password)

# Генерация API ключа
api_key = security_service.generate_api_key()

# Валидация пароля
security_service.validate_password_strength("SecurePass123")
```

### 3. Dependencies (`app/auth/dependencies.py`)

FastAPI зависимости для защиты endpoints.

**Основные зависимости:**

- `get_current_user` - получает текущего пользователя из JWT токена
- `get_current_active_user` - получает активного пользователя
- `get_current_admin_user` - получает администратора
- `require_api_key` - аутентификация через API ключ (заголовок X-API-Key)
- `get_optional_current_user` - опциональная аутентификация (возвращает None если нет токена)
- `get_db` - получает сессию базы данных

**Пример использования в endpoints:**

```python
from fastapi import Depends
from app.auth.dependencies import (
    get_current_user,
    get_current_admin_user,
    require_api_key
)

# Требует любой валидный токен
@router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"user_id": user.id}

# Требует активного пользователя
@router.get("/user-profile")
async def profile(user: User = Depends(get_current_active_user)):
    return {"username": user.username}

# Требует администратора
@router.delete("/users/{user_id}")
async def delete_user(user: User = Depends(get_current_admin_user)):
    # Только администратор может удалять пользователей
    pass

# Требует API ключ
@router.get("/api-endpoint")
async def api_endpoint(user: User = Depends(require_api_key)):
    return {"api_key_user": user.username}
```

## API Endpoints

### POST /api/v1/auth/register

Регистрация нового пользователя.

**Request Body:**

```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "SecurePass123"
}
```

**Requirements:**

- `username`: 3-50 символов, только буквы, цифры, подчеркивания и дефисы
- `email`: валидный email адрес
- `password`: минимум 8 символов, содержит заглавную/строчные буквы и цифру

**Response (201):**

```json
{
  "id": 1,
  "username": "newuser",
  "email": "newuser@example.com",
  "settings": null,
  "created_at": "2026-02-05T12:00:00"
}
```

**Errors:**

- `400 Bad Request`: email или username уже заняты, слабый пароль
- `422 Unprocessable Entity`: неверный формат данных

**Пример:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"newuser@example.com","password":"SecurePass123"}'
```

---

### POST /api/v1/auth/login

Аутентификация пользователя и получение токенов.

Использует OAuth2 Password Flow.

**Request Body (form-data):**

```
username: newuser
password: SecurePass123
```

Примечание: Можно использовать email или username в поле `username`.

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**

- `401 Unauthorized`: неверные учетные данные
- `403 Forbidden`: аккаунт неактивен

**Пример:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=newuser&password=SecurePass123"
```

---

### POST /api/v1/auth/refresh

Обновление access токена с помощью refresh токена.

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  // тот же refresh токен
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**

- `401 Unauthorized`: невалидный или истекший refresh токен

**Пример:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"your_refresh_token_here"}'
```

---

### GET /api/v1/auth/me

Получение информации о текущем пользователе.

**Headers:**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200):**

```json
{
  "id": 1,
  "username": "newuser",
  "email": "newuser@example.com",
  "settings": null,
  "created_at": "2026-02-05T12:00:00"
}
```

**Errors:**

- `401 Unauthorized`: невалидный или отсутствующий токен

**Пример:**

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer your_access_token_here"
```

## Безопасность

### Защита sensitive данных

- Пароли никогда не возвращаются в API ответах
- API ключи никогда не возвращаются в API ответах
- Хешированные пароли используются только для проверки

### Валидация паролей

Пароли проверяются на:
- Минимальную длину (8 символов)
- Наличие заглавных и строчных букв
- Наличие цифр
- Отсутствие в списке слабых паролей

### HTTP статусы ошибок

- `401 Unauthorized` - проблемы с аутентификацией
- `403 Forbidden` - проблемы с авторизацией (недостаточно прав, неактивный аккаунт)
- `422 Unprocessable Entity` - неверный формат данных

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# Только unit тесты
pytest tests/auth/test_jwt_service.py
pytest tests/auth/test_security_service.py
pytest tests/auth/test_dependencies.py

# Только интеграционные тесты
pytest tests/auth/test_auth_endpoints.py

# С покрытием
pytest --cov=app/auth --cov=app/api/v1/auth.py
```

### Unit тесты

**JWT Service tests:**
- Создание access токена
- Создание refresh токена
- Валидация корректных токенов
- Обработка истекших токенов
- Обработка некорректных токенов
- Проверка типа токена (access/refresh)

**Security Service tests:**
- Хеширование паролей
- Проверка паролей
- Генерация API ключей
- Валидация сложности паролей
- Валидация email

**Dependencies tests:**
- `get_current_user` с валидным токеном
- `get_current_user` с невалидным токеном
- `get_current_active_user` с активным/неактивным пользователем
- `get_current_admin_user` с admin/non-admin
- `require_api_key` с валидным/невалидным API ключом

### Интеграционные тесты

**POST /api/v1/auth/register:**
- Успешная регистрация
- Дубликаты email
- Дубликаты username
- Слабые пароли
- Невалидный email формат
- Короткий username
- Недопустимые символы в username

**POST /api/v1/auth/login:**
- Успешный логин с username
- Успешный логин с email
- Неверный пароль
- Не существующий пользователь
- Неактивный пользователь

**POST /api/v1/auth/refresh:**
- Успешный refresh
- Истекший токен
- Невалидный токен
- Refresh с access токеном

**GET /api/v1/auth/me:**
- Успешный запрос с валидным токеном
- Запрос без токена
- Запрос с невалидным токеном
- Запрос с истекшим токеном

## Использование в других endpoints

### Защита endpoint с JWT токеном

```python
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_active_user
from app.database.models.user import User

router = APIRouter()

@router.get("/tasks")
async def get_tasks(user: User = Depends(get_current_active_user)):
    # Доступно только авторизованным активным пользователям
    return {"tasks": [...]}
```

### Защита endpoint только для администраторов

```python
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin_user)
):
    # Доступно только администраторам
    pass
```

### Защита endpoint с API ключом

```python
@router.get("/api/endpoint")
async def api_endpoint(user: User = Depends(require_api_key)):
    # Альтернативный способ аутентификации через API ключ
    return {"user": user.username}
```

### Опциональная аутентификация

```python
from app.auth.dependencies import get_optional_current_user

@router.get("/public-endpoint")
async def public_endpoint(user: Optional[User] = Depends(get_optional_current_user)):
    if user:
        return {"message": f"Hello, {user.username}!"}
    return {"message": "Hello, guest!"}
```

## OpenAPI документация

Все endpoints автоматически документируются в OpenAPI/Swagger UI:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Endpoints аутентификации находятся в секции "Authentication".

## Примеры работы с API

### Регистрация и логин

```python
import httpx

# 1. Регистрация
response = httpx.post("http://localhost:8000/api/v1/auth/register", json={
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "SecurePass123"
})
user_data = response.json()

# 2. Логин
response = httpx.post("http://localhost:8000/api/v1/auth/login", data={
    "username": "newuser",
    "password": "SecurePass123"
})
token_data = response.json()

# 3. Использование токена для доступа к защищенному endpoint
headers = {"Authorization": f"Bearer {token_data['access_token']}"}
response = httpx.get("http://localhost:8000/api/v1/auth/me", headers=headers)
print(response.json())
```

### Использование refresh токена

```python
# 4. Обновление access токена
response = httpx.post("http://localhost:8000/api/v1/auth/refresh", json={
    "refresh_token": token_data['refresh_token']
})
new_token_data = response.json()

# 5. Использование нового access токена
headers = {"Authorization": f"Bearer {new_token_data['access_token']}"}
response = httpx.get("http://localhost:8000/api/v1/auth/me", headers=headers)
```

## Production рекомендации

1. **Безопасность:**
   - Используйте сильный секретный ключ для JWT (минимум 32 символа)
   - Храните секретный ключ в переменных окружения
   - Используйте HTTPS в production
   - Настройте CORS ограничения

2. **Database:**
   - Используйте Alembic migrations для управления схемой
   - Регулярно делайте backups базы данных

3. **Токены:**
   - Храните refresh токены в защищенном хранилище (HttpOnly cookies)
   - Реализуйте logout/blacklist refresh токенов
   - Мониторьте использование токенов

4. **Мониторинг:**
   - Логируйте попытки авторизации
   - Мониторите подозрительную активность
   - Настройте rate limiting для auth endpoints

## Troubleshooting

### Ошибка "Could not validate credentials"

- Проверьте, что токен не истек
- Убедитесь, что используете правильный секретный ключ
- Проверьте формат заголовка: `Authorization: Bearer <token>`

### Ошибка "Inactive user"

- Аккаунт пользователя деактивирован администратором
- Свяжитесь с поддержкой для активации аккаунта

### Ошибка "Not enough permissions"

- Endpoint требует права администратора
- Убедитесь, что у вашего аккаунта есть права `is_admin=True`

## Дополнительные материалы

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OAuth2 with Password Flow](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [python-jose documentation](https://python-jose.readthedocs.io/)
- [passlib documentation](https://passlib.readthedocs.io/)
