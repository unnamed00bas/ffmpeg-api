# Примеры использования API

Ниже приведены практические примеры использования FFmpeg API.

## Содержание

- [Аутентификация](#аутентификация)
  - [Регистрация нового пользователя](#регистрация-нового-пользователя)
  - [Вход в систему](#вход-в-систему)
  - [Обновление токена](#обновление-токена)
  - [Получение информации о текущем пользователе](#получение-информации-о-текущем-пользователе)
- [Примеры работы с задачами](#примеры-работы-с-задачами)
  - [Объединение видео](#объединение-видео)
  - [Наложение текста](#наложение-текста)
  - [Наложение аудио](#наложение-аудио)
  - [Наложение видео (PiP)](#наложение-видео-pip)
  - [Комбинированные операции](#комбинированные-операции)
  - [Субтитры](#субтитры)
- [Полный рабочий процесс](#полный-рабочий-процесс)

---

## Аутентификация

### Регистрация нового пользователя

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "SecurePassword123"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 123,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_admin": false,
  "is_active": true,
  "created_at": "2026-02-05T10:30:00Z"
}
```

**Ответ (ошибка, 400 - дубликат email):**
```json
{
  "detail": "Email already registered"
}
```

**Ответ (ошибка, 422 - слабый пароль):**
```json
{
  "detail": "Password must be at least 8 characters with uppercase, lowercase, and number"
}
```

### Вход в систему

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=newuser@example.com&password=SecurePassword123"
```

**Ответ (успех, 200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Ответ (ошибка, 401):**
```json
{
  "detail": "Incorrect email/username or password"
}
```

### Обновление токена

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Ответ (успех, 200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Получение информации о текущем пользователе

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Ответ (успех, 200):**
```json
{
  "id": 123,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_admin": false,
  "is_active": true,
  "created_at": "2026-02-05T10:30:00Z",
  "settings": {}
}
```

**Ответ (ошибка, 401 - недействительный токен):**
```json
{
  "detail": "Could not validate credentials"
}
```

---

## Примеры работы с задачами

### Объединение видео

**Важно:** Для объединения нужно минимум 2 видеофайла.

```bash
curl -X POST http://localhost:8000/api/v1/tasks/join \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": [1, 2, 3],
    "output_filename": "joined_video.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 456,
  "type": "join",
  "status": "pending",
  "user_id": 123,
  "input_files": [1, 2, 3],
  "output_files": [],
  "config": {
    "output_filename": "joined_video.mp4"
  },
  "progress": 0.0,
  "error_message": null,
  "result": null,
  "retry_count": 0,
  "created_at": "2026-02-05T10:35:00Z",
  "updated_at": "2026-02-05T10:35:00Z"
}
```

**Ответ (ошибка, 422 - недостаточно файлов):**
```json
{
  "detail": "At least 2 files required for join operation"
}
```

### Наложение текста

```bash
curl -X POST http://localhost:8000/api/v1/tasks/text-overlay \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "video_file_id": 1,
    "text": "Watermark Text",
    "position": {
      "type": "relative",
      "position": "center",
      "margin_x": 50,
      "margin_y": 50
    },
    "style": {
      "font_family": "Arial",
      "font_size": 24,
      "color": "#FFFFFF"
    },
    "background": {
      "enabled": true,
      "color": "#000000",
      "opacity": 0.5
    },
    "output_filename": "watermarked.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 457,
  "type": "text_overlay",
  "status": "pending",
  "user_id": 123,
  "config": {
    "video_file_id": 1,
    "text": "Watermark Text",
    "position": {
      "type": "relative",
      "x": 50,
      "y": 50
    },
    "style": {
      "font_family": "Arial",
      "font_size": 24,
      "font_color": "#FFFFFF"
    },
    "output_filename": "watermarked.mp4"
  },
  "created_at": "2026-02-05T10:40:00Z"
}
```

### Наложение аудио

```bash
curl -X POST http://localhost:8000/api/v1/tasks/audio-overlay \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "video_file_id": 1,
    "audio_file_id": "https://example.com/audio.mp3", // Можно использовать URL
    "mode": "replace",
    "overlay_volume": 1.0,
    "output_filename": "audio_overlayed.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 458,
  "type": "audio_overlay",
  "status": "pending",
  "user_id": 123,
  "config": {
    "video_file_id": 1,
    "audio_file_id": 5,
    "mode": "replace",
    "overlay_volume": 1.0,
    "output_filename": "audio_overlayed.mp4"
  },
  "created_at": "2026-02-05T10:45:00Z"
}
```

**Параметры mode:**
- `replace` - заменить аудиодорожку
- `mix` - смешать с существующим аудио

### Наложение видео (Picture-in-Picture)

```bash
curl -X POST http://localhost:8000/api/v1/tasks/video-overlay \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "base_video_file_id": 1,
    "overlay_video_file_id": 6,
    "config": {
      "x": 10,
      "y": 10,
      "width": 200,
      "height": 150,
      "opacity": 1.0
    },
    "output_filename": "pip_video.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 459,
  "type": "video_overlay",
  "status": "pending",
  "user_id": 123,
  "config": {
    "base_video_file_id": 1,
    "overlay_video_file_id": 6,
    "config": {
      "x": 10,
      "y": 10,
      "width": 200,
      "height": 150,
      "opacity": 1.0
    },
    "output_filename": "pip_video.mp4"
  },
  "created_at": "2026-02-05T10:50:00Z"
}
```

### Комбинированные операции

Выполнение нескольких операций подряд:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/combined \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "base_file_id": 1,
    "operations": [
      {
        "type": "text_overlay",
        "config": {
          "text": "First Watermark",
          "position": {
            "type": "relative",
            "position": "top-left",
            "margin_x": 100,
            "margin_y": 100
          },
          "style": {
            "font_size": 24,
            "color": "#FFFFFF"
          }
        }
      },
      {
        "type": "text_overlay",
        "config": {
          "text": "Second Watermark",
          "position": {
            "type": "relative",
            "position": "bottom-right",
            "margin_x": 200,
            "margin_y": 200
          },
          "style": {
            "font_size": 20,
            "color": "#00FF00"
          }
        }
      },
      {
        "type": "audio_overlay",
        "config": {
          "audio_file_id": 5,
          "mode": "mix",
          "overlay_volume": 0.8
        }
      }
    ],
    "output_filename": "combined_output.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 460,
  "type": "combined",
  "status": "pending",
  "user_id": 123,
  "config": {
    "base_file_id": 1,
    "operations": [
      {
        "type": "text_overlay",
        "config": {
          "text": "First Watermark",
          "position": {"x": 100, "y": 100}
        }
      },
      {
        "type": "text_overlay",
        "config": {
          "text": "Second Watermark",
          "position": {"x": 200, "y": 200}
        }
      },
      {
        "type": "audio_overlay",
        "config": {
          "audio_file_id": 5,
          "mode": "mix",
          "overlay_volume": 0.8
        }
      }
    ],
    "output_filename": "combined_output.mp4"
  },
  "created_at": "2026-02-05T11:00:00Z"
}
```

### Субтитры

```bash
curl -X POST http://localhost:8000/api/v1/tasks/subtitles \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "video_file_id": 1,
    "subtitle_text": [
        {"start": 0, "end": 2, "text": "This is a subtitle"}
    ],
    "style": {
      "font_name": "Arial",
      "font_size": 20,
      "primary_color": "&H00FFFFFF",
      "back_color": "&H80000000"
    },
    "output_filename": "subtitled.mp4"
  }'
```

**Ответ (успех, 201):**
```json
{
  "id": 461,
  "type": "subtitle",
  "status": "pending",
  "user_id": 123,
  "config": {
    "video_file_id": 1,
    "subtitle_text": "This is a subtitle",
    "position": "bottom",
    "style": {
      "font_family": "Arial",
      "font_size": 20
    },
    "timing": {
      "start_time": 0,
      "end_time": 5
    },
    "output_filename": "subtitled.mp4"
  },
  "created_at": "2026-02-05T11:05:00Z"
}
```

---

## Полный рабочий процесс

Ниже приведен полный пример рабочего процесса от регистрации до получения результата обработки видео.

```bash
#!/bin/bash

# 1. Регистрация нового пользователя
echo "Step 1: Registering user..."
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "workflow_user",
    "email": "workflow@example.com",
    "password": "Workflow123"
  }')

echo "Register response: $REGISTER_RESPONSE"

# 2. Вход в систему
echo "Step 2: Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=workflow@example.com&password=Workflow123")

echo "Login response: $LOGIN_RESPONSE"

# Извлечение токена
TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Access token: ${TOKEN:0:50}..."

# 3. Загрузка видеофайла
echo "Step 3: Uploading video file..."
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video1.mp4")

echo "Upload response: $UPLOAD_RESPONSE"
FILE_ID_1=$(echo $UPLOAD_RESPONSE | jq -r '.id')
echo "Uploaded file ID: $FILE_ID_1"

# Загрузка второго видеофайла для объединения
echo "Step 4: Uploading second video file..."
UPLOAD_RESPONSE_2=$(curl -s -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video2.mp4")

FILE_ID_2=$(echo $UPLOAD_RESPONSE_2 | jq -r '.id')
echo "Uploaded file ID: $FILE_ID_2"

# 5. Создание задачи на объединение видео
echo "Step 5: Creating join task..."
TASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/tasks/join \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_ids\": [$FILE_ID_1, $FILE_ID_2],
    \"output_filename\": \"joined_output.mp4\"
  }")

echo "Task response: $TASK_RESPONSE"
TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')
echo "Created task ID: $TASK_ID"

# 6. Проверка статуса задачи (поллинг)
echo "Step 6: Checking task status..."
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  STATUS_RESPONSE=$(curl -s -X GET http://localhost:8000/api/v1/tasks/$TASK_ID \
    -H "Authorization: Bearer $TOKEN")

  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  PROGRESS=$(echo $STATUS_RESPONSE | jq -r '.progress')

  echo "Status: $STATUS, Progress: $PROGRESS%"

  if [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
    break
  fi

  WAIT_COUNT=$((WAIT_COUNT + 1))
  sleep 1
done

# 7. Получение деталей задачи
echo "Step 7: Getting task details..."
TASK_DETAILS=$(curl -s -X GET http://localhost:8000/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN")

echo "Task details: $TASK_DETAILS"

# Проверка результата
RESULT=$(echo $TASK_DETAILS | jq -r '.result')
echo "Task result: $RESULT"

# 8. Скачивание результата (если задача выполнена успешно)
if [ "$STATUS" == "completed" ] && [ "$RESULT" != "null" ]; then
  echo "Step 8: Downloading result..."
  OUTPUT_FILE_ID=$(echo $RESULT | jq -r '.output_file')

  curl -X GET http://localhost:8000/api/v1/files/$OUTPUT_FILE_ID/download \
    -H "Authorization: Bearer $TOKEN" \
    -o "result_video.mp4"

  echo "Result downloaded to: result_video.mp4"
else
  echo "Task failed or is still processing"
fi

# 9. Получение списка всех файлов пользователя
echo "Step 9: Getting user files..."
FILES_RESPONSE=$(curl -s -X GET "http://localhost:8000/api/v1/files?limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN")

echo "Files: $FILES_RESPONSE"

# 10. Получение статистики пользователя
echo "Step 10: Getting user statistics..."
STATS_RESPONSE=$(curl -s -X GET http://localhost:8000/api/v1/users/me/stats \
  -H "Authorization: Bearer $TOKEN")

echo "User statistics: $STATS_RESPONSE"

# 11. Выход (обновление токена если нужно)
echo "Step 11: Refreshing token..."
REFRESH_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": $(echo $LOGIN_RESPONSE | jq -r '.refresh_token')}")

NEW_TOKEN=$(echo $REFRESH_RESPONSE | jq -r '.access_token')
echo "New token: ${NEW_TOKEN:0:50}..."

echo "Workflow completed!"
```

### Пример с Python

```python
import httpx
import asyncio
from pathlib import Path

async def full_workflow():
    """Полный рабочий процесс с использованием Python"""
    
    base_url = "http://localhost:8000/api/v1"
    
    async with httpx.AsyncClient() as client:
        # 1. Регистрация
        register = await client.post(
            f"{base_url}/auth/register",
            json={
                "username": "python_user",
                "email": "python@example.com",
                "password": "Python123"
            }
        )
        print(f"Register: {register.status_code}")
        assert register.status_code == 201
        
        # 2. Логин
        login = await client.post(
            f"{base_url}/auth/login",
            data={
                "username": "python@example.com",
                "password": "Python123"
            }
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        
        client.headers["Authorization"] = f"Bearer {token}"
        
        # 3. (Optional) Загрузка файла
        # Для примера используем URL в задаче, поэтому загрузка не обязательна
        # video_path = Path("/path/to/video.mp4")
        # with open(video_path, "rb") as f:
        #     upload = await client.post(...)
        # file_id = upload.json()["id"]
        
        # 4. Создание задачи с использованием URL
        video_url = "https://example.com/video.mp4"
        task = await client.post(
            f"{base_url}/tasks/text-overlay",
            json={
                "video_file_id": video_url,
                "text": "Python Watermark",
                "position": {"type": "relative", "position": "center"},
                "style": {"font_size": 24, "color": "#FFFFFF"},
                "output_filename": "watermarked.mp4"
            }
        )
        assert task.status_code == 201
        task_id = task.json()["id"]
        
        # 5. Поллинг статуса
        while True:
            status = await client.get(f"{base_url}/tasks/{task_id}")
            status_data = status.json()
            
            print(f"Status: {status_data['status']}, Progress: {status_data['progress']}%")
            
            if status_data['status'] in ['completed', 'failed']:
                break
            
            await asyncio.sleep(2)
        
        # 6. Проверка результата
        if status_data['status'] == 'completed':
            print("Task completed successfully!")
            print(f"Result: {status_data['result']}")
        else:
            print(f"Task failed: {status_data['error_message']}")
        
        # 7. Получение списка файлов
        files = await client.get(f"{base_url}/files")
        print(f"Total files: {files.json()['total']}")

# Запуск
asyncio.run(full_workflow())
```

### Коды HTTP ответов

| Код | Значение | Действие |
|------|----------|----------|
| 200 | OK | Запрос выполнен успешно |
| 201 | Created | Ресурс успешно создан |
| 204 | No Content | Успешное удаление, нет содержимого для возврата |
| 400 | Bad Request | Неверный формат запроса |
| 401 | Unauthorized | Требуется аутентификация или токен недействителен |
| 403 | Forbidden | Недостаточно прав |
| 404 | Not Found | Ресурс не найден |
| 422 | Unprocessable Entity | Ошибка валидации данных |
| 429 | Too Many Requests | Превышен лимит запросов (rate limiting) |
| 500 | Internal Server Error | Внутренняя ошибка сервера |

### Полезные советы

1. **Сохраняйте токен** для повторного использования в рамках сессии
2. **Обновляйте токен** перед истечением срока действия (по умолчанию 30 минут)
3. **Используйте refresh_token** для получения нового access_token без повторного логина
4. **Проверяйте статус задачи** периодически вместо ожидания
5. **Обрабатывайте ошибки** gracefully, проверяя коды ответов
6. **Используйте пагинацию** для больших списков файлов и задач
7. **Фильтруйте результаты** по статусу, типу задачи и т.д.

---

## Дополнительные ресурсы

- [Полная документация API](./API.md)
- [Архитектура системы](./ARCHITECTURE.md)
- [Руководство по деплою](./DEPLOYMENT.md)
- [Устранение неполадок](./TROUBLESHOOTING.md)
- [Swagger/OpenAPI UI](http://localhost:8000/docs)

---

**Последнее обновление:** 2026-02-05
