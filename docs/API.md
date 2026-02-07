# API Документация FFmpeg Service

## Base URL

```
https://api.ffmpeg-service.com/api/v1
```

## Аутентификация

Все защищенные эндпоинты требуют заголовок:

```
Authorization: Bearer <JWT_TOKEN>
```

## Конвенции ответов

### Успешный ответ
API возвращает JSON объект, соответствующий схеме ответа (Pydantic model).
Поле `success` и обертка `data` отсутствуют (за исключением специфических случаев, если указано иначе).

Пример:
```json
{
  "id": 123,
  "username": "john_doe",
  "email": "john@example.com"
}
```

### Ошибка
```json
{
  "detail": "Error description"
}
```
Или, в случае ошибок валидации:
```json
{
  "detail": [
    {
      "loc": ["body", "field"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Пагинация
Ответы списков обычно имеют структуру:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```
(Проверьте конкретный endpoint для точной структуры, например `TaskResponse` завернут в `TaskListResponse` с полями `tasks`, `total`, `page`, `page_size`).

---

## Auth Endpoints

### POST /auth/register
Регистрация нового пользователя

**Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password123"
}
```

**Response (201):**
```json
{
  "id": 123,
  "username": "john_doe",
  "email": "john@example.com",
  "is_admin": false,
  "is_active": true,
  "settings": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### POST /auth/login
Вход в систему

**Body:**
```json
{
  "username": "john_doe",
  "password": "secure_password123"
}
```
(Content-Type: application/x-www-form-urlencoded или json, зависит от реализации OAuth2, обычно form-data username/password)

**Response (200):**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "refresh_token": "refresh_token_here",
  "expires_in": 1800
}
```

### POST /auth/refresh
Обновление токена

**Body:**
```json
{
  "refresh_token": "refresh_token_here"
}
```

**Response (200):**
```json
{
  "access_token": "new_jwt_token_here",
  "token_type": "bearer",
  "refresh_token": "new_refresh_token_here",
  "expires_in": 1800
}
```

### GET /auth/me
Получение информации о текущем пользователе

**Response (200):**
```json
{
  "id": 123,
  "username": "john_doe",
  "email": "john@example.com",
  "is_admin": false,
  "is_active": true,
  "settings": { ... },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

## Работа с файлами (File Inputs)

Во всех эндпоинтах создания задач, где требуется указать файл (например, `video_file_id`, `audio_file_id`, `base_file_id`), API поддерживает два формата:

1.  **ID файла (Integer):** Идентификатор ранее загруженного файла.
2.  **URL файла (String):** Прямая ссылка на файл (http/https). Файл будет скачан автоматически перед началом обработки.

Пример использования URL:
```json
{
  "video_file_id": "https://example.com/video.mp4",
  ...
}
```

---

## Tasks Endpoints

### POST /tasks/join
Объединение нескольких видео в один

**Body:**
```json
{
  "file_ids": [
    123,
    "https://example.com/video2.mp4"
  ],
  "output_filename": "joined_output.mp4",
  "priority": 5
}
```

**Параметры:**
| Параметр | Тип | Обязательно | Описание |
|---|---|---|---|
| `file_ids` | List[int/str] | Да | Список ID файлов или URL (минимум 2) |
| `output_filename` | str | Нет | Имя выходного файла |
| `priority` | int | Нет | Приоритет (1-10, по умолчанию 5) |

**Response (201):**
```json
{
  "id": 1,
  "user_id": 123,
  "type": "join",
  "status": "pending",
  "input_files": [123, 456],
  "output_files": [],
  "config": {
    "file_ids": [...],
    "output_filename": "joined_output.mp4"
  },
  "error_message": null,
  "progress": 0.0,
  "result": null,
  "retry_count": 0,
  "priority": 5,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "completed_at": null
}
```

### POST /tasks/audio-overlay
Наложение аудио на видео

**Body:**
```json
{
  "video_file_id": 123,
  "audio_file_id": "https://example.com/audio.mp3",
  "mode": "replace",  // "replace" или "mix"
  "offset": 0.0,      // Смещение начала аудио в секундах (>= 0)
  "duration": null,   // Длительность накладываемого аудио (опционально)
  "original_volume": 1.0, // Громкость ориг. аудио (0.0 - 2.0)
  "overlay_volume": 1.0,  // Громкость накладываемого аудио (0.0 - 2.0)
  "output_filename": "output.mp4",
  "priority": 5
}
```

**Параметры:**
| Параметр | Тип | Обязательно | Описание |
|---|---|---|---|
| `video_file_id` | int/str | Да | ID или URL видеофайла |
| `audio_file_id` | int/str | Да | ID или URL аудиофайла |
| `mode` | str | Нет | `replace` (замена) или `mix` (смешивание). Default: `replace` |
| `offset` | float | Нет | Смещение аудио в сек (>= 0) |
| `duration` | float | Нет | Длительность накладываемого аудио (опционально) |
| `original_volume` | float | Нет | Громкость исходного видео (0.0 - 2.0). Default: 1.0 |
| `overlay_volume` | float | Нет | Громкость накладываемого аудио (0.0 - 2.0). Default: 1.0 |

**Response (201):** Как у /tasks/join

### POST /tasks/text-overlay
Наложение текста на видео

**Body:**
```json
{
  "video_file_id": 123,
  "text": "Hello World",
  "position": {
    "type": "relative",
    "position": "top-left", // "top-left", "top-center", "top-right", "center-left", "center", ...
    "margin_x": 10,
    "margin_y": 10
  },
  "style": {
    "font_family": "Arial",
    "font_size": 24,
    "font_weight": "bold",
    "color": "#FFFFFF",
    "alpha": 1.0
  },
  "background": {
    "enabled": true,
    "color": "#000000",
    "alpha": 0.5,
    "padding": 10,
    "border_radius": 5
  },
  "border": {
    "enabled": false,
    "width": 2,
    "color": "#000000"
  },
  "shadow": {
    "enabled": false,
    "offset_x": 2,
    "offset_y": 2,
    "blur": 2,
    "color": "#000000"
  },
  "animation": {
    "type": "fade_in",
    "duration": 1.0,
    "delay": 0.0
  },
  "rotation": 0,
  "opacity": 1.0,
  "start_time": 0.0,
  "end_time": 5.0,
  "output_filename": "text_output.mp4",
  "priority": 5
}
```

**Параметры:**
| Параметр | Тип | Обязательно | Описание |
|---|---|---|---|
| `video_file_id` | int/str | Да | ID или URL видеофайла |
| `text` | str | Да | Текст для наложения |
| `position` | obj | Нет | Объект позиционирования (`type`, `position`, `margin_x`, `margin_y`) |
| `style` | obj | Нет | Объект стилей (`font_family`, `font_size`, `color`, `alpha`, `font_weight`) |
| `background` | obj | Нет | Объект фона (`enabled`, `color`, `alpha`, `padding`, `border_radius`) |
| `animation` | obj | Нет | Объект анимации (`type`, `duration`, `delay`) |

**Response (201):** Как у /tasks/join

### POST /tasks/subtitles
Наложение субтитров на видео

**Body:**
```json
{
  "video_file_id": 123,
  "subtitle_file_id": "https://example.com/subs.srt", // Optional if subtitle_text provided
  "subtitle_text": [ // Optional if subtitle_file_id provided
      {
        "start": 0.0,
        "end": 2.5,
        "text": "Hello world"
      }
  ],
  "format": "SRT",  // SRT, VTT, ASS, SSA
  "style": {
      "font_name": "Arial",
      "font_size": 20,
      "primary_color": "&H00FFFFFF",
      "back_color": "&H80000000",
      "bold": false,
      "italic": false,
      "border_style": 1,
      "outline": 2.0,
      "shadow": 2.0,
      "alignment": 2,
      "margin_l": 10,
      "margin_r": 10,
      "margin_v": 10
  },
  "position": {
      "position": "bottom",
      "margin_y": 10
  },
  "output_filename": "subtitled_output.mp4",
  "priority": 5
}
```

**Параметры:**
| Параметр | Тип | Обязательно | Описание |
|---|---|---|---|
| `video_file_id` | int/str | Да | ID или URL видеофайла |
| `subtitle_file_id` | int/str | * | ID/URL файла субтитров (*обязательно, если нет subtitle_text) |
| `subtitle_text` | list | * | Список объектов субтитров (*обязательно, если нет subtitle_file_id) |
| `format` | str | Нет | `SRT`, `VTT`, `ASS`, `SSA` (Default: SRT) |
| `style` | obj | Нет | Стили (для ASS/SSA) |
| `position` | obj | Нет | Позиционирование (`position`, `margin_y`) |

**Response (201):** Как у /tasks/join

### POST /tasks/video-overlay
Наложение видео поверх видео (Picture-in-Picture)

**Body:**
```json
{
  "base_video_file_id": 123,
  "overlay_video_file_id": "https://example.com/overlay.mp4",
  "config": {
    "x": 10,
    "y": 10,
    "width": 320,
    "height": 240,
    "scale": 0.5,
    "opacity": 1.0,
    "shape": "rectangle", // "rectangle", "circle", "rounded"
    "border_radius": 0
  },
  "border": {
    "enabled": true,
    "width": 2,
    "color": "#FFFFFF"
  },
  "shadow": {
    "enabled": true,
    "offset_x": 2,
    "offset_y": 2,
    "blur": 2,
    "color": "#000000"
  },
  "output_filename": "pip_output.mp4",
  "priority": 5
}
```

**Параметры:**
| Параметр | Тип | Обязательно | Описание |
|---|---|---|---|
| `base_video_file_id` | int/str | Да | ID или URL основного видео |
| `overlay_video_file_id` | int/str | Да | ID или URL видео для наложения |
| `config` | obj | Нет | Конфигурация (`x`, `y`, `width`, `height`, `opacity`, `scale`, `shape`, `border_radius`) |
| `border` | obj | Нет | Настройки рамки (`enabled`, `width`, `color`) |
| `shadow` | obj | Нет | Настройки тени (`enabled`, `offset_x`, `offset_y`, `blur`, `color`) |

**Response (201):** Как у /tasks/join

### POST /tasks/combined
Комбинированная операция (несколько типов обработки)

**Body:**
```json
{
  "base_file_id": 123,
  "operations": [
    {
      "type": "text_overlay",
      "config": { ... }  // конфигурация как в text-overlay (без поля video_file_id)
    },
    {
      "type": "audio_overlay",
      "config": { ... }  // конфигурация как в audio-overlay (без поля video_file_id)
    }
  ],
  "output_filename": "combined_output.mp4",
  "priority": 5
}
```

**Response (201):** Как у /tasks/join

### GET /tasks/{task_id}
Получение статуса задачи

**Response (200):**
```json
{
  "id": 1,
  "user_id": 123,
  "type": "text_overlay",
  "status": "processing",
  "progress": 45.0,
  "priority": 5,
  "created_at": "...",
  "updated_at": "...",
  "completed_at": null,
  "config": { ... },
  "result": null,
  "error_message": null,
  "retry_count": 0
}
```

**Status values:**
- `pending` - В очереди
- `processing` - В обработке
- `completed` - Завершено успешно
- `failed` - Ошибка
- `cancelled` - Отменено

### GET /tasks
Список задач пользователя

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 20, max: 100)
- `status` (optional)
- `type` (optional)
- `sort_by` (default: created_at)
- `sort_order` (default: desc)

**Response (200):**
```json
{
  "tasks": [
    { ... } // TaskResponse objects
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### DELETE /tasks/{task_id}
Отмена задачи

**Response (200):**
```json
{
  "message": "Task cancelled"
}
```
(Или объект TaskResponse, зависит от реализации, обычно просто статус или message).

### POST /tasks/{task_id}/retry
Повторная обработка задачи

**Response (200):**
```json
{ ... } // Updated TaskResponse
```

---

## Files Endpoints

### POST /files/upload
Загрузка файла

**Request:** multipart/form-data
- `file`: файл
- `metadata` (optional): JSON строка

**Response (201):**
```json
{
  "id": 123,
  "user_id": 1,
  "filename": "video.mp4",
  "original_name": "video.mp4",
  "file_size": 1024000,
  "mime_type": "video/mp4",
  "storage_path": "...",
  "url": "http://minio...",
  "created_at": "...",
  "updated_at": "..."
}
```

### POST /files/upload-by-url
Загрузка файла по URL

**Body:**
```json
{
  "url": "https://example.com/video.mp4",
  "filename": "video.mp4"
}
```

**Response (201):** Как у /files/upload

### GET /files/{file_id}/download
Скачивание файла

**Response (200):** Файл (application/octet-stream)

### DELETE /files/{file_id}
Удаление файла

**Response (200):**
```json
{
  "success": true
}
``` 
(или HTTP 204 No Content, проверьте реализацию)

---

## Users Endpoints

### GET /users/me/settings
Получение настроек пользователя

**Response (200):**
```json
{
  "settings": { ... },
  "created_at": "...",
  "updated_at": "..."
}
```

### PUT /users/me/settings
Обновление настроек пользователя

**Body:**
```json
{
  "default_output_format": "mp4"
  // ... другие настройки
}
```

**Response (200):** Как у GET /users/me/settings

### GET /users/me/stats
Статистика пользователя

**Response (200):**
```json
{
  "total_tasks": 150,
  "completed_tasks": 130,
  "failed_tasks": 15,
  "processing_tasks": 5,
  "total_files": 50,
  "storage_used": 5368709120,
  "storage_limit": 10737418240
}
```

### GET /users/me/history
История задач пользователя

**Query Parameters:** Как у GET /tasks

**Response (200):** Как у GET /tasks (TaskListResponse)

---

## Admin Endpoints

### GET /admin/tasks
Получение списка всех задач

**Response (200):** TaskListResponse

### GET /admin/users
Получение списка пользователей

**Response (200):**
```json
{
  "users": [...],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

### GET /admin/metrics
Метрики системы

**Response (200):**
```json
{
  "tasks_completed": 1000,
  "active_workers": 10,
  ...
}
```

### GET /admin/queue-status
Статус очереди

**Response (200):**
```json
{
  "pending": 25,
  "processing": 10,
  "failed": 5
}
```

### POST /admin/cleanup
Ручная очистка старых файлов

**Response (200):**
```json
{
  "deleted_count": 150,
  "freed_space": 5368709120
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `401` | Unauthorized - Требуется указать Bearer token |
| `403` | Forbidden - Недостаточно прав |
| `404` | Not Found - Ресурс не найден |
| `422` | Validation Error - Ошибка в данных запроса |
| `500` | Internal Server Error - Ошибка на сервере |


## Base URL

```
https://api.ffmpeg-service.com/api/v1
```

## Аутентификация

Все защищенные эндпоинты требуют заголовок:

```
Authorization: Bearer <JWT_TOKEN>
```

## Конвенции ответов

### Успешный ответ
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

### Ошибка
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": { ... }
  }
}
```

### Пагинация
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

---

## Auth Endpoints

### POST /auth/register
Регистрация нового пользователя

**Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password123"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "username": "john_doe",
      "email": "john@example.com"
    },
    "token": "jwt_token_here"
  }
}
```

### POST /auth/login
Вход в систему

**Body:**
```json
{
  "username": "john_doe",
  "password": "secure_password123"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "jwt_token_here",
    "refresh_token": "refresh_token_here",
    "user": { ... }
  }
}
```

### POST /auth/refresh
Обновление токена

**Body:**
```json
{
  "refresh_token": "refresh_token_here"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "new_jwt_token_here",
    "refresh_token": "new_refresh_token_here"
  }
}
```

### GET /auth/me
Получение информации о текущем пользователе

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "api_key": "api_key_here",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

## Работа с файлами (File Inputs)

Во всех эндпоинтах создания задач, где требуется указать файл (например, `video_file_id`, `audio_file_id`, `base_file_id`), API поддерживает два формата:

1.  **ID файла (Integer):** Идентификатор ранее загруженного файла.
2.  **URL файла (String):** Прямая ссылка на файл (http/https). Файл будет скачан автоматически перед началом обработки.

Пример использования URL:
```json
{
  "video_file_id": "https://example.com/video.mp4",
  ...
}
```

---

## Tasks Endpoints

### POST /tasks/join
Объединение нескольких видео в один

**Body:**
```json
{
  "videos": [
    {
      "source": "file_upload",
      "file_id": 123
    },
    {
      "source": "url",
      "url": "https://example.com/video2.mp4"
    }
    // Или упрощенный формат (список ID или URL):
    // "file_ids": [123, "https://example.com/video2.mp4"]
  ],
  "output_config": {
    "format": "mp4",
    "video_codec": "libx264",
    "audio_codec": "aac",
    "resolution": "1920x1080",
    "bitrate": "5000k",
    "preset": "fast"
  },
  "priority": 5
}
```

**Response (202):**
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "type": "join",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### POST /tasks/audio-overlay
Наложение аудио на видео

**Body:**
```json
{
  "video_file_id": 123,
  "audio_file_id": "https://example.com/audio.mp3",
  "mode": "replace",  // "replace" или "mix"
  "mix_volume": 0.7,  // для mode="mix"
  "start_offset": 0,  // начало аудио в секундах
  "output_config": { ... },
  "priority": 5
}
```

**Response (202):** Как у /tasks/join

### POST /tasks/text-overlay
Наложение текста на видео

**Body:**
```json
{
  "video_file_id": 123,
  "output_config": { ... },
  "text": "Hello World\nSecond Line",
  "start_time": 0,
  "end_time": 5,
  "position": {
    "x": 50,
    "y": 50,
    "anchor": "top_left"
  },
  "style": {
    "name": "Arial",
    "size": 48,
    "color": "#FFFFFF",
    "weight": "bold",
    "family": "Arial"
  },
  "background": {
    "enabled": true,
    "color": "#000000",
    "opacity": 0.7,
    "padding": 10,
    "radius": 5
  },
  "border": {
    "enabled": true,
    "width": 3,
    "color": "#000000"
  },
  "shadow": {
    "enabled": true,
    "offset_x": 2,
    "offset_y": 2,
    "blur": 5,
    "color": "#000000",
    "opacity": 0.8
  },
  "animation": {
    "type": "fade_in_out",
    "duration": 0.5
  },
  "rotation": 0,
  "opacity": 1.0,
  "priority": 5
}
```

**Response (202):** Как у /tasks/join

### POST /tasks/subtitles
Наложение субтитров на видео

**Body:**
```json
{
  "video_file_id": 123,
  "output_config": { ... },
  "subtitle_file_id": "https://example.com/subs.srt", // Optional if subtitle_text is provided
  "subtitle_text": [ // Optional if subtitle_file_id is provided
      {
        "start": 0,
        "end": 2,
        "text": "Привет, мир!"
      }
  ],
  "format": "srt",  // "srt", "vtt", "ass"
  "style": {
      "font_name": "Arial",
      "font_size": 24,
      "primary_color": "&H00FFFFFF",
      "back_color": "&H80000000",
      "bold": true,
      "border_style": 1,
      "outline": 2,
      "shadow": 2,
      "alignment": 2,
      "margin_l": 10,
      "margin_r": 10,
      "margin_v": 10
  },
  "position": {
      "position": "bottom",
      "margin_y": 10
  },
  "priority": 5
}
```

**Response (202):** Как у /tasks/join

### POST /tasks/video-overlay
Наложение видео поверх видео (Picture-in-Picture)

**Body:**
```json
{
  "base_video_file_id": 123,
  "overlay_video_file_id": "https://example.com/overlay.mp4",
  "overlay_position": {
    "x": 10,
    "y": 10,
    "width": 320,
    "height": 240,
    "anchor": "top_left"
  },
  "shape": "rectangle",  // "rectangle", "circle", "rounded"
  "radius": 10,  // для shape="rounded"
  "opacity": 1.0,
  "border": {
    "enabled": true,
    "width": 2,
    "color": "#FFFFFF"
  },
  "shadow": {
    "enabled": true,
    "blur": 10,
    "offset_x": 5,
    "offset_y": 5,
    "color": "#000000"
  },
  "start_time": 0,
  "end_time": 10,
  "output_config": { ... },
  "priority": 5
}
```

**Response (202):** Как у /tasks/join

### POST /tasks/combined
Комбинированная операция (несколько типов обработки)

**Body:**
```json
{
  "base_file_id": 123,
  "operations": [
    {
      "type": "text_overlay",
      "config": { ... }  // конфигурация для text_overlay
    },
    {
      "type": "audio_overlay",
      "config": { ... }  // конфигурация для audio_overlay
    },
    {
      "type": "subtitles",
      "config": { ... }  // конфигурация для subtitles
    }
  ],
  "output_config": { ... },
  "priority": 5
}
```

**Response (202):** Как у /tasks/join

### GET /tasks/{task_id}
Получение статуса задачи

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "type": "text_overlay",
    "status": "processing",
    "progress": 45,
    "priority": 5,
    "created_at": "2024-01-01T00:00:00Z",
    "started_at": "2024-01-01T00:00:01Z",
    "completed_at": null,
    "error_message": null,
    "output_file": null,
    "retry_count": 0
  }
}
```

**Status values:**
- `pending` - В очереди
- `processing` - В обработке
- `completed` - Завершено успешно
- `failed` - Ошибка
- `cancelled` - Отменено

### GET /tasks
Список задач пользователя

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 20, max: 100)
- `status` (optional): pending, processing, completed, failed, cancelled
- `type` (optional): join, audio_overlay, text_overlay, subtitles, video_overlay, combined
- `sort_by` (default: created_at)
- `sort_order` (default: desc)

**Response (200):**
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### DELETE /tasks/{task_id}
Отмена задачи

**Response (200):**
```json
{
  "success": true,
  "message": "Task cancelled successfully"
}
```

### POST /tasks/{task_id}/retry
Повторная обработка задачи

**Response (200):**
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "retry_count": 1
  }
}
```

---

## Files Endpoints

### POST /files/upload
Загрузка файла

**Request:** multipart/form-data
- `file`: файл
- `metadata` (optional): JSON строка с метаданными

**Response (200):**
```json
{
  "success": true,
  "data": {
    "file_id": "uuid",
    "original_name": "video.mp4",
    "file_size": 1024000,
    "mime_type": "video/mp4",
    "storage_path": "minio_bucket/path/to/file",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### POST /files/upload-by-url
Загрузка файла по URL

**Body:**
```json
{
  "url": "https://example.com/video.mp4",
  "metadata": { ... }
}
```

**Response (200):** Как у /files/upload

### GET /files/{file_id}/download
Скачивание файла

**Response (200):** Файл (application/octet-stream)

### DELETE /files/{file_id}
Удаление файла

**Response (200):**
```json
{
  "success": true,
  "message": "File deleted successfully"
}
```

---

## Users Endpoints

### GET /users/me/settings
Получение настроек пользователя

**Response (200):**
```json
{
  "success": true,
  "data": {
    "default_output_format": "mp4",
    "default_video_codec": "libx264",
    "default_audio_codec": "aac",
    "default_resolution": "1920x1080",
    "max_file_size": 1073741824,
    "storage_retention_days": 7,
    "api_settings": { ... }
  }
}
```

### PUT /users/me/settings
Обновление настроек пользователя

**Body:**
```json
{
  "default_output_format": "mp4",
  "default_video_codec": "libx264",
  "default_audio_codec": "aac",
  "default_resolution": "1920x1080",
  "max_file_size": 1073741824,
  "storage_retention_days": 7,
  "api_settings": { ... }
}
```

**Response (200):** Как у GET /users/me/settings

### GET /users/me/stats
Статистика пользователя

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_tasks": 150,
    "completed_tasks": 130,
    "failed_tasks": 15,
    "pending_tasks": 5,
    "total_storage_used": 5368709120,
    "avg_processing_time": 45.2,
    "storage_used_by_status": {
      "pending": 536870912,
      "processing": 1073741824,
      "completed": 3758096384
    }
  }
}
```

### GET /users/me/history
История задач пользователя (с пагинацией)

**Query Parameters:** Как у GET /tasks

**Response (200):** Как у GET /tasks

---

## Admin Endpoints

### GET /admin/tasks
Получение списка всех задач (для администраторов)

**Query Parameters:** Как у GET /tasks + `user_id` (optional)

**Response (200):** Как у GET /tasks

### GET /admin/users
Получение списка пользователей

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 20)
- `search` (optional): поиск по username или email

**Response (200):**
```json
{
  "success": true,
  "data": [...],
  "pagination": { ... }
}
```

### GET /admin/metrics
Метрики системы

**Query Parameters:**
- `from` (optional): ISO 8601 datetime
- `to` (optional): ISO 8601 datetime

**Response (200):**
```json
{
  "success": true,
  "data": {
    "tasks_completed": 1000,
    "tasks_failed": 50,
    "avg_processing_time": 45.2,
    "total_storage_used": 10737418240,
    "queue_size": 25,
    "active_workers": 10,
    "cpu_usage": 75.5,
    "memory_usage": 68.3
  }
}
```

### GET /admin/queue-status
Статус очереди задач

**Response (200):**
```json
{
  "success": true,
  "data": {
    "pending_tasks": 25,
    "processing_tasks": 10,
    "failed_tasks": 5,
    "by_priority": {
      "high": 3,
      "normal": 15,
      "low": 7
    },
    "by_type": {
      "join": 5,
      "audio_overlay": 8,
      "text_overlay": 10,
      "subtitles": 5,
      "video_overlay": 7,
      "combined": 5
    }
  }
}
```

### POST /admin/cleanup
Ручная очистка старых файлов

**Body:**
```json
{
  "older_than_days": 7,
  "status": "completed"  // или "all"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "files_deleted": 150,
    "space_freed": 5368709120
  }
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `AUTH_REQUIRED` | Требуется аутентификация |
| `INVALID_TOKEN` | Недействительный токен |
| `TOKEN_EXPIRED` | Токен истек |
| `PERMISSION_DENIED` | Недостаточно прав |
| `VALIDATION_ERROR` | Ошибка валидации данных |
| `FILE_NOT_FOUND` | Файл не найден |
| `FILE_TOO_LARGE` | Файл слишком большой |
| `INVALID_FILE_TYPE` | Неподдерживаемый тип файла |
| `TASK_NOT_FOUND` | Задача не найдена |
| `TASK_ALREADY_COMPLETED` | Задача уже завершена |
| `TASK_CANNOT_BE_CANCELLED` | Задачу нельзя отменить |
| `MAX_RETRIES_EXCEEDED` | Превышено количество попыток |
| `FFMPEG_ERROR` | Ошибка FFmpeg |
| `STORAGE_ERROR` | Ошибка хранения |
| `RATE_LIMIT_EXCEEDED` | Превышен лимит запросов |
| `INTERNAL_ERROR` | Внутренняя ошибка сервера |

---

## Примеры использования

### Полный пример обработки видео

```bash
# 1. Загрузка файла
curl -X POST https://api.ffmpeg-service.com/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@video.mp4"

# Ответ: {"file_id": "uuid"}

# 2. Создание задачи наложения текста
curl -X POST https://api.ffmpeg-service.com/api/v1/tasks/text-overlay \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "video": {"source": "file_upload", "file_id": "uuid"},
    "output_config": {
      "format": "mp4",
      "video_codec": "libx264",
      "audio_codec": "aac"
    },
    "text_overlays": [
      {
        "text": "Hello World",
        "start_time": 0,
        "end_time": 5,
        "position": {"x": 50, "y": 50, "anchor": "top_left"},
        "font": {"name": "Arial", "size": 48, "color": "#FFFFFF"}
      }
    ]
  }'

# Ответ: {"task_id": "uuid"}

# 3. Проверка статуса задачи
curl https://api.ffmpeg-service.com/api/v1/tasks/uuid \
  -H "Authorization: Bearer YOUR_TOKEN"

# Ответ: {"status": "processing", "progress": 45}

# 4. Когда статус "completed", скачивание файла
curl https://api.ffmpeg-service.com/api/v1/files/output_uuid/download \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o output.mp4
```
