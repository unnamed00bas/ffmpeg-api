# FFmpeg API Service

REST API сервис для асинхронной обработки видео файлов с использованием FFmpeg.

## Возможности

- 🎬 **Объединение видео** - склеивание нескольких видео файлов в один
- 🎵 **Наложение аудио** - замена или микс аудио дорожки с синхронизацией по времени
- ✏️ **Наложение текста** - добавление текста на видео с полной кастомизацией
- 📝 **Субтитры** - генерация и наложение субтитров (SRT, VTT, ASS/SSA)
- 🖼️ **Picture-in-Picture** - наложение видео поверх видео
- 🔄 **Комбинированные операции** - одновременное применение нескольких эффектов
- ⚡ **Асинхронная обработка** - очереди задач с приоритетами
- 📊 **Мониторинг** - метрики, логирование, дашборды
- 🚀 **Масштабируемость** - горизонтальное масштабирование
- 🔐 **Аутентификация** - JWT токены и API ключи

## Технологический стек

- **Backend**: Python 3.11+, FastAPI
- **Task Queue**: Redis + Celery
- **Database**: PostgreSQL 15+
- **Storage**: MinIO (S3-compatible)
- **Video Processing**: FFmpeg 4.4+
- **Monitoring**: Prometheus + Grafana
- **Containerization**: Docker + Docker Compose

## Быстрый старт

### Требования

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ RAM
- 20GB+ свободного диска

### Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd ffmpeg-api
```

2. Скопируйте и отредактируйте .env файл:
```bash
cp .env.example .env
nano .env
```

3. Запустите сервисы:
```bash
docker-compose up -d
```

4. Инициализируйте базу данных:
```bash
docker-compose exec api python scripts/init_db.py
```

5. Создайте admin пользователя:
```bash
docker-compose exec api python scripts/create_admin.py
```

6. Проверьте работоспособность:
```bash
curl http://localhost:8000/api/v1/health
```

## Использование API

### Пример: Наложение текста на видео

```bash
# 1. Загрузка файла
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@video.mp4"

# Получите file_id из ответа

# 2. Создание задачи
curl -X POST http://localhost:8000/api/v1/tasks/text-overlay \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "video": {"source": "file_upload", "file_id": "YOUR_FILE_ID"},
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

# Получите task_id из ответа

# 3. Проверка статуса
curl http://localhost:8000/api/v1/tasks/YOUR_TASK_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. Скачивание результата (когда status="completed")
curl http://localhost:8000/api/v1/files/OUTPUT_FILE_ID/download \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o output.mp4
```

## Документация

- [Архитектура](docs/ARCHITECTURE.md) - детальное описание архитектуры
- [API Документация](docs/API.md) - полное описание API endpoints
- [Deployment Guide](docs/DEPLOYMENT.md) - руководство по развертыванию

## Доступные сервисы

| Сервис | URL | Назначение |
|--------|-----|------------|
| API | http://localhost:8000 | REST API |
| Grafana | http://localhost:3000 | Дашборды мониторинга |
| Prometheus | http://localhost:9090 | Метрики |
| Flower | http://localhost:5555 | Мониторинг Celery |
| MinIO Console | http://localhost:9001 | Управление хранилищем |

## Структура проекта

```
ffmpeg-api/
├── app/                      # Основное приложение
│   ├── api/                  # API endpoints
│   ├── models/               # SQLAlchemy модели
│   ├── schemas/              # Pydantic схемы
│   ├── services/             # Бизнес-логика
│   ├── processors/           # FFmpeg процессоры
│   ├── database/             # Database layer
│   ├── storage/              # MinIO интеграция
│   ├── queue/                # Celery задачи
│   ├── middleware/           # Custom middleware
│   ├── utils/                # Утилиты
│   └── monitoring/           # Логирование и метрики
├── docker/                   # Docker конфигурации
├── tests/                    # Тесты
├── scripts/                  # Скрипты (backup, init)
├── docs/                     # Документация
├── docker-compose.yml        # Development compose
└── docker-compose.prod.yml   # Production compose
```

## Production развертывание

Подробная информация в [Deployment Guide](docs/DEPLOYMENT.md)

Краткий обзор:

1. Настройте SSL сертификаты (Let's Encrypt)
2. Настройте .env.production
3. Запустите с production compose файлом:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Масштабирование

### API Servers
```bash
docker-compose up -d --scale api=5
```

### Workers
```bash
docker-compose up -d --scale worker=10
```

## Мониторинг

Доступны следующие метрики:

- Время обработки задач
- Размер входных/выходных файлов
- Процент успешных операций
- Размер очереди задач
- CPU/Memory использование

Просмотр через Grafana на http://localhost:3000

## Поддерживаемые форматы

### Входные форматы
- Видео: MP4, AVI, MOV, MKV, WMV
- Аудио: MP3, AAC, WAV, FLAC, OGG
- Субтитры: SRT, VTT, ASS, SSA

### Выходные форматы
- Видео: MP4, AVI, MOV, MKV, WebM
- Аудио: AAC, MP3, FLAC, Opus
- Кодеки: H.264, H.265/HEVC, VP8, VP9

## Безопасность

- JWT токены для аутентификации
- Rate limiting
- Валидация всех входных данных
- Изолированные Docker контейнеры
- HTTPS/TLS шифрование (production)

## Contributing

1. Fork репозитория
2. Создайте feature ветку (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в ветку (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## License

MIT License

## Контакты

Для вопросов и поддержки создайте issue в репозитории.
