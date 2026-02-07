# Этап 5: Тестирование и деплой (Недели 11-12)

## Обзор этапа

Этап завершает разработку проекта полноценным тестированием, достижением покрытия кода > 80%, подготовкой полной документации, настройкой production окружения с Nginx и SSL сертификатами, и созданием CI/CD pipeline для автоматизации.

---

## Подзадача 5.1: Unit тесты (расширение)

### Задачи реализации

**Структура директории тестов:**

```
tests/
├── conftest.py              # общие fixtures
├── api/                     # API endpoints тесты
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_files.py
│   ├── test_tasks.py
│   ├── test_users.py
│   └── test_admin.py
├── services/                # бизнес-логика тесты
│   ├── __init__.py
│   ├── test_auth_service.py
│   ├── test_file_service.py
│   ├── test_task_service.py
│   └── test_cache_service.py
├── processors/              # FFmpeg процессоры тесты
│   ├── __init__.py
│   ├── test_video_joiner.py
│   ├── test_audio_overlay.py
│   ├── test_text_overlay.py
│   ├── test_subtitle_processor.py
│   ├── test_video_overlay.py
│   └── test_combined_processor.py
├── repositories/            # репозитории тесты
│   ├── __init__.py
│   ├── test_user_repository.py
│   ├── test_task_repository.py
│   └── test_file_repository.py
├── integration/             # интеграционные тесты
│   ├── __init__.py
│   ├── test_ffmpeg.py
│   ├── test_minio.py
│   ├── test_database.py
│   └── test_redis.py
├── e2e/                   # end-to-end тесты
│   ├── __init__.py
│   ├── test_full_workflow.py
│   └── test_task_lifecycle.py
└── load/                   # нагрузочные тесты
    ├── locustfile.py
    └── README.md
```

**Конфигурация pytest в [pytest.ini](pytest.ini):**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
    --asyncio-mode=auto
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
    requires_ffmpeg: Tests requiring FFmpeg
    requires_network: Tests requiring network access
```

**Общие fixtures в [tests/conftest.py](tests/conftest.py):**

```python
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.models.base import Base
from app.database.connection import get_db
from app.auth.security import SecurityService

# Async client fixture
@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# Database fixture
@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Test user fixture
@pytest.fixture
async def test_user(db_session):
    from app.database.models.user import User
    
    hashed_password = SecurityService.hash_password("testpassword123")
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        is_active=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user

# Auth token fixture
@pytest.fixture
async def auth_token(test_user):
    from app.auth.jwt import JWTService
    
    jwt_service = JWTService()
    token = jwt_service.create_access_token(test_user.id)
    return token

# Authorized client fixture
@pytest.fixture
async def authorized_client(client: AsyncClient, auth_token: str):
    client.headers = {"Authorization": f"Bearer {auth_token}"}
    yield client

# Admin user fixture
@pytest.fixture
async def admin_user(db_session):
    from app.database.models.user import User
    
    hashed_password = SecurityService.hash_password("adminpassword123")
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashed_password,
        is_admin=True,
        is_active=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user

# Test file fixture
@pytest.fixture
async def test_file(test_user, db_session):
    from app.database.models.file import File
    
    file = File(
        user_id=test_user.id,
        filename="test/file.mp4",
        original_filename="test.mp4",
        size=1024,
        content_type="video/mp4",
        metadata={"duration": 10.0}
    )
    
    db_session.add(file)
    await db_session.commit()
    await db_session.refresh(file)
    
    return file

# Temp file fixture
@pytest.fixture
def temp_video_file(tmp_path):
    """Создание временного видео файла"""
    import cv2
    
    file_path = tmp_path / "test_video.mp4"
    
    # Создание простого видео (5 секунд, 30fps, 640x480)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(
        str(file_path),
        fourcc,
        30.0,
        (640, 480)
    )
    
    for _ in range(150):  # 5 секунд * 30 fps
        frame = cv2.UMat(480, 640, 3)
        out.write(frame)
    
    out.release()
    
    return str(file_path)
```

**Unit тесты API endpoints в [tests/api/](tests/api/):**

*[tests/api/test_auth.py](tests/api/test_auth.py):*

```python
import pytest
from httpx import AsyncClient

class TestAuthEndpoints:
    
    @pytest.mark.unit
    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert "created_at" in data
    
    @pytest.mark.unit
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different",
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.unit
    async def test_login_success(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email_or_username": "test@example.com",
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.unit
    async def test_login_invalid_credentials(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email_or_username": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.unit
    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.unit
    async def test_get_me_authorized(self, authorized_client: AsyncClient, test_user):
        response = await authorized_client.get("/api/v1/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
```

*[tests/api/test_files.py](tests/api/test_files.py):*

```python
import pytest
from httpx import AsyncClient

class TestFilesEndpoints:
    
    @pytest.mark.unit
    async def test_upload_file_success(
        self,
        authorized_client: AsyncClient,
        temp_video_file: str
    ):
        with open(temp_video_file, "rb") as f:
            response = await authorized_client.post(
                "/api/v1/files/upload",
                files={"file": ("test.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "filename" in data
    
    @pytest.mark.unit
    async def test_upload_file_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/files/upload",
            files={"file": ("test.txt", b"content", "text/plain")}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.unit
    async def test_get_files_success(
        self,
        authorized_client: AsyncClient,
        test_file
    ):
        response = await authorized_client.get("/api/v1/files")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) >= 1
    
    @pytest.mark.unit
    async def test_delete_file_success(
        self,
        authorized_client: AsyncClient,
        test_file
    ):
        response = await authorized_client.delete(f"/api/v1/files/{test_file.id}")
        
        assert response.status_code == 204
```

*[tests/api/test_tasks.py](tests/api/test_tasks.py):*

```python
import pytest
from httpx import AsyncClient

class TestTasksEndpoints:
    
    @pytest.mark.unit
    async def test_create_task_success(
        self,
        authorized_client: AsyncClient,
        test_file
    ):
        response = await authorized_client.post(
            "/api/v1/tasks",
            json={
                "type": "join",
                "config": {},
                "file_ids": [test_file.id]
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["type"] == "join"
        assert data["status"] == "pending"
    
    @pytest.mark.unit
    async def test_get_task_success(
        self,
        authorized_client: AsyncClient,
        test_task
    ):
        response = await authorized_client.get(f"/api/v1/tasks/{test_task.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_task.id
```

**Unit тесты сервисов в [tests/services/](tests/services/):**

*[tests/services/test_file_service.py](tests/services/test_file_service.py):*

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestFileService:
    
    @pytest.mark.unit
    async def test_upload_file_success(self, db_session, test_user):
        from app.services.file_service import FileService
        
        mock_minio = Mock()
        mock_minio.upload_file = AsyncMock(return_value="test/object.mp4")
        
        service = FileService(db_session, mock_minio)
        
        file = await service.upload_from_request(
            user_id=test_user.id,
            filename="object.mp4",
            content=b"fake content",
            content_type="video/mp4"
        )
        
        assert file is not None
        assert file.user_id == test_user.id
        assert file.original_filename == "object.mp4"
        mock_minio.upload_file.assert_called_once()
```

**Unit тесты процессоров в [tests/processors/](tests/processors/):**

*[tests/processors/test_video_joiner.py](tests/processors/test_video_joiner.py):*

```python
import pytest
from unittest.mock import Mock, patch

class TestVideoJoiner:
    
    @pytest.mark.unit
    @pytest.mark.requires_ffmpeg
    async def test_validate_input_success(
        self,
        db_session,
        test_user,
        temp_video_file
    ):
        from app.processors.video_joiner import VideoJoiner
        from app.database.models.file import File
        
        # Создание тестовых файлов
        file1 = File(
            user_id=test_user.id,
            filename=f"file1.mp4",
            original_filename="file1.mp4",
            size=1024,
            content_type="video/mp4",
            metadata={"duration": 10.0}
        )
        file2 = File(
            user_id=test_user.id,
            filename=f"file2.mp4",
            original_filename="file2.mp4",
            size=1024,
            content_type="video/mp4",
            metadata={"duration": 10.0}
        )
        
        db_session.add_all([file1, file2])
        await db_session.commit()
        
        processor = VideoJoiner(
            task_id=1,
            config={
                "file_ids": [file1.id, file2.id]
            },
            progress_callback=None
        )
        
        # Should not raise
        await processor.validate_input()
    
    @pytest.mark.unit
    async def test_create_concat_list(self, db_session, test_user):
        from app.processors.video_joiner import VideoJoiner
        
        processor = VideoJoiner(
            task_id=1,
            config={},
            progress_callback=None
        )
        
        concat_list = await processor._create_concat_list([
            "file1.mp4",
            "file2.mp4"
        ])
        
        with open(concat_list, "r") as f:
            content = f.read()
            assert "file 'file1.mp4'" in content
            assert "file 'file2.mp4'" in content
```

**Development requirements в [requirements-dev.txt](requirements-dev.txt):**

```txt
# Testing
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0
pytest-mock==3.12.0
pytest-xdist==3.5.0

# HTTP client
httpx==0.25.0

# Code coverage
coverage==7.3.0

# Mocking
unittest-mock==1.0.1

# Async testing
anyio==3.7.1

# Locust for load testing
locust==2.17.0
```

### Тестирование подзадачи 5.1

**Запуск unit тестов:**

```bash
# Все unit тесты
pytest tests/ -m unit

# Конкретный файл
pytest tests/api/test_auth.py

# С coverage
pytest tests/ --cov=app --cov-report=html

# С coverage fail under 80%
pytest tests/ --cov=app --cov-fail-under=80

# Параллельный запуск (ускорение)
pytest tests/ -n auto
```

**Проверка coverage:**

- Open coverage report: `htmlcov/index.html`
- Проверить coverage > 80%
- Проверить покрытие критических модулей > 90%
- Проверить отсутствие uncovered критических путей

**CI/CD интеграция:**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run linting
        run: |
          black --check app/
          flake8 app/
          mypy app/
      
      - name: Run tests
        run: |
          pytest tests/ -m unit --cov=app --cov-report=xml --cov-fail-under=80
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests
          name: codecov-umbrella
      
      - name: Upload coverage artifacts
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report
          path: htmlcov/
```

---

## Подзадача 5.2: Integration тесты

### Задачи реализации

**FFmpeg integration тесты в [tests/integration/test_ffmpeg.py](tests/integration/test_ffmpeg.py):**

```python
import pytest
import subprocess
import os

@pytest.mark.integration
@pytest.mark.requires_ffmpeg
class TestFFmpegIntegration:
    
    async def test_ffmpeg_installed(self):
        """Проверка что FFmpeg установлен"""
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True
        )
        
        assert result.returncode == 0
        assert "ffmpeg version" in result.stderr.decode()
    
    async def test_ffprobe_installed(self):
        """Проверка что FFprobe установлен"""
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True
        )
        
        assert result.returncode == 0
        assert "ffprobe version" in result.stderr.decode()
    
    async def test_simple_ffmpeg_command(self, temp_video_file):
        """Простая FFmpeg команда"""
        output_file = temp_video_file.replace(".mp4", "_output.mp4")
        
        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-c", "copy",
            output_file,
            "-y"
        ], capture_output=True)
        
        assert result.returncode == 0
        assert os.path.exists(output_file)
    
    async def test_get_video_info(self, temp_video_file):
        """Получение информации о видео"""
        from app.ffmpeg.commands import FFmpegCommand
        
        info = await FFmpegCommand.get_video_info(temp_video_file)
        
        assert info is not None
        assert "duration" in info
        assert "width" in info
        assert "height" in info
        assert "video_codec" in info
    
    async def test_video_join(self, temp_video_file):
        """Объединение двух видео"""
        output_file = temp_video_file.replace(".mp4", "_joined.mp4")
        
        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-i", temp_video_file,
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1[outv]",
            "-map", "[outv]",
            output_file,
            "-y"
        ], capture_output=True)
        
        assert result.returncode == 0
        assert os.path.exists(output_file)
        
        # Проверка что длительность удвоилась
        info = await FFmpegCommand.get_video_info(output_file)
        original_info = await FFmpegCommand.get_video_info(temp_video_file)
        assert abs(info["duration"] - 2 * original_info["duration"]) < 0.5
```

**MinIO integration тесты в [tests/integration/test_minio.py](tests/integration/test_minio.py):**

```python
import pytest
from minio import Minio
from minio.error import S3Error

@pytest.mark.integration
@pytest.mark.requires_network
class TestMinIOIntegration:
    
    @pytest.fixture
    async def minio_client(self):
        """Создание MinIO клиента для тестов"""
        client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
        
        # Создание тестового бакета
        bucket_name = "test-bucket"
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        yield client
        
        # Очистка
        objects = client.list_objects(bucket_name)
        for obj in objects:
            client.remove_object(bucket_name, obj.object_name)
        client.remove_bucket(bucket_name)
    
    async def test_upload_file(self, minio_client):
        """Загрузка файла"""
        file_content = b"test content"
        minio_client.put_object(
            "test-bucket",
            "test.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )
        
        # Проверка что файл загружен
        objects = minio_client.list_objects("test-bucket")
        assert len(objects) == 1
        assert objects[0].object_name == "test.txt"
    
    async def test_download_file(self, minio_client):
        """Скачивание файла"""
        file_content = b"download test"
        
        minio_client.put_object(
            "test-bucket",
            "download.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )
        
        # Скачивание
        data = minio_client.get_object("test-bucket", "download.txt")
        downloaded = data.read()
        
        assert downloaded == file_content
    
    async def test_delete_file(self, minio_client):
        """Удаление файла"""
        minio_client.put_object(
            "test-bucket",
            "delete.txt",
            io.BytesIO(b"delete me"),
            length=9
        )
        
        # Удаление
        minio_client.remove_object("test-bucket", "delete.txt")
        
        # Проверка
        objects = minio_client.list_objects("test-bucket")
        assert len(objects) == 0
    
    async def test_generate_presigned_url(self, minio_client):
        """Генерация presigned URL"""
        file_content = b"presigned test"
        
        minio_client.put_object(
            "test-bucket",
            "presigned.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )
        
        # Генерация URL
        url = minio_client.presigned_get_object(
            "test-bucket",
            "presigned.txt",
            expires=timedelta(hours=1)
        )
        
        assert "localhost:9000" in url
        assert "presigned.txt" in url
```

**Database integration тесты в [tests/integration/test_database.py](tests/integration/test_database.py):**

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.mark.integration
class TestDatabaseIntegration:
    
    @pytest.fixture
    async def test_engine(self):
        """Создание тестового движка БД"""
        engine = create_async_engine(
            "postgresql+asyncpg://postgres_user:postgres_password@localhost:5432/test_db"
        )
        
        yield engine
        
        await engine.dispose()
    
    @pytest.fixture
    async def test_session(self, test_engine):
        """Создание тестовой сессии"""
        async_session = sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            yield session
    
    async def test_connection(self, test_engine):
        """Проверка соединения с БД"""
        async with test_engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            assert result.scalar() == 1
    
    async def test_transaction_rollback(self, test_session):
        """Проверка rollback транзакции"""
        from app.database.models.user import User
        from app.auth.security import SecurityService
        
        hashed_password = SecurityService.hash_password("test")
        user = User(
            username="transaction_test",
            email="transaction@test.com",
            hashed_password=hashed_password
        )
        
        test_session.add(user)
        
        # Rollback
        await test_session.rollback()
        
        # Проверка что пользователь не сохранен
        result = await test_session.execute(
            select(User).where(User.username == "transaction_test")
        )
        assert result.scalar_one_or_none() is None
    
    async def test_transaction_commit(self, test_session):
        """Проверка commit транзакции"""
        from app.database.models.user import User
        from app.auth.security import SecurityService
        
        hashed_password = SecurityService.hash_password("test")
        user = User(
            username="commit_test",
            email="commit@test.com",
            hashed_password=hashed_password
        )
        
        test_session.add(user)
        await test_session.commit()
        
        # Проверка что пользователь сохранен
        result = await test_session.execute(
            select(User).where(User.username == "commit_test")
        )
        assert result.scalar_one_or_none() is not None
```

**E2E тесты в [tests/e2e/](tests/e2e/):**

```python
import pytest
from httpx import AsyncClient

@pytest.mark.e2e
class TestFullWorkflow:
    
    async def test_complete_user_workflow(
        self,
        client: AsyncClient,
        temp_video_file
    ):
        """Полный workflow пользователя"""
        
        # 1. Регистрация
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "workflow_user",
                "email": "workflow@example.com",
                "password": "workflow123"
            }
        )
        assert register_response.status_code == 201
        
        # 2. Логин
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email_or_username": "workflow@example.com",
                "password": "workflow123"
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # 3. Загрузка файла
        client.headers = {"Authorization": f"Bearer {token}"}
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("workflow.mp4", f, "video/mp4")}
            )
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]
        
        # 4. Создание задачи
        task_response = await client.post(
            "/api/v1/tasks",
            json={
                "type": "join",
                "config": {},
                "file_ids": [file_id]
            }
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]
        
        # 5. Проверка статуса задачи
        import asyncio
        await asyncio.sleep(5)  # Ожидание обработки
        
        status_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert status_response.status_code == 200
        task = status_response.json()
        assert task["status"] in ["completed", "processing", "failed"]
```

### Тестирование подзадачи 5.2

**Запуск integration тестов:**

```bash
# Все integration тесты
pytest tests/integration/ -m integration

# Конкретный тест
pytest tests/integration/test_ffmpeg.py

# С Docker Compose
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/
docker-compose -f docker-compose.test.yml down
```

**Запуск e2e тестов:**

```bash
# Все e2e тесты
pytest tests/e2e/ -m e2e

# Конкретный тест
pytest tests/e2e/test_full_workflow.py
```

---

## Подзадача 5.3: Load testing

### Задачи реализации

**Locust файл в [tests/load/locustfile.py](tests/load/locustfile.py):**

```python
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random

class FFmpegAPIUser(HttpUser):
    """Симуляция пользователя API"""
    
    wait_time = between(1, 5)
    
    def on_start(self):
        """Выполняется при старте каждого пользователя"""
        # Регистрация и логин
        self.client.post("/api/v1/auth/register", json={
            "username": f"user_{random.randint(1000, 9999)}",
            "email": f"user{random.randint(1000, 9999)}@example.com",
            "password": "password123"
        })
        
        response = self.client.post("/api/v1/auth/login", json={
            "email_or_username": "test@example.com",
            "password": "testpassword123"
        })
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
    
    @task(3)
    def get_tasks(self):
        """Получение списка задач (чаще)"""
        self.client.get("/api/v1/tasks")
    
    @task(2)
    def get_files(self):
        """Получение списка файлов"""
        self.client.get("/api/v1/files")
    
    @task(1)
    def get_user_stats(self):
        """Получение статистики пользователя"""
        self.client.get("/api/v1/users/me/stats")

class CreateTaskUser(HttpUser):
    """Симуляция пользователя создающего задачи"""
    
    wait_time = between(5, 15)
    
    def on_start(self):
        # Логин (используем существующего пользователя)
        response = self.client.post("/api/v1/auth/login", json={
            "email_or_username": "test@example.com",
            "password": "testpassword123"
        })
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
            
            # Загрузка тестового файла (предполагаем что файл существует)
            self.test_file_id = self._upload_test_file()
    
    def _upload_test_file(self):
        """Загрузка тестового файла"""
        import os
        test_file = "tests/fixtures/test_video.mp4"
        
        if os.path.exists(test_file):
            with open(test_file, "rb") as f:
                response = self.client.post(
                    "/api/v1/files/upload",
                    files={"file": ("test.mp4", f, "video/mp4")}
                )
            
            if response.status_code == 201:
                return response.json()["id"]
        
        return None
    
    @task
    def create_join_task(self):
        """Создание задачи на объединение видео"""
        if self.test_file_id:
            self.client.post("/api/v1/tasks", json={
                "type": "join",
                "config": {},
                "file_ids": [self.test_file_id]
            })
    
    @task
    def create_audio_overlay_task(self):
        """Создание задачи на наложение аудио"""
        if self.test_file_id:
            self.client.post("/api/v1/tasks", json={
                "type": "audio_overlay",
                "config": {
                    "video_file_id": self.test_file_id,
                    "audio_file_id": self.test_file_id,
                    "mode": "replace"
                },
                "file_ids": [self.test_file_id, self.test_file_id]
            })

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Выполняется после завершения теста"""
    if environment.stats.total.fail_ratio > 0.05:
        print(f"\n❌ High failure rate: {environment.stats.total.fail_ratio:.2%}")
        print("Optimization needed!")
    else:
        print(f"\n✅ Acceptable failure rate: {environment.stats.total.fail_ratio:.2%}")
    
    if environment.stats.total.avg_response_time > 500:
        print(f"⚠️  High average response time: {environment.stats.total.avg_response_time:.2f}ms")
    else:
        print(f"✅ Good average response time: {environment.stats.total.avg_response_time:.2f}ms")
```

**README для load testing в [tests/load/README.md](tests/load/README.md):**

```markdown
# Load Testing with Locust

## Установка

```bash
pip install locust
```

## Запуск тестов

### Стандартный режим (100 пользователей)

```bash
locust -f tests/load/locustfile.py --users 100 --spawn-rate 10
```

### Веб интерфейс

```bash
locust -f tests/load/locustfile.py
```

Затем откройте http://localhost:8089

### Distributed режим (для больших нагрузок)

**Master:**
```bash
locust -f tests/load/locustfile.py --master
```

**Worker:**
```bash
locust -f tests/load/locustfile.py --worker --master-host=<master-ip>
```

## Метрики

- Requests per second (RPS)
- Response time (p50, p95, p99)
- Failure rate
- CPU, RAM, Disk, Network usage

## Цели

- Успешная обработка 100+ concurrent requests
- Failure rate < 5%
- P95 response time < 500ms
- P99 response time < 1000ms
```

### Тестирование подзадачи 5.3

**Запуск load тестов:**

```bash
# Стандартный режим
locust -f tests/load/locustfile.py --users 100 --spawn-rate 10 -t 5m

# Веб интерфейс
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Stress тестирование (500 пользователей)
locust -f tests/load/locustfile.py --users 500 --spawn-rate 50 -t 10m
```

**Анализ метрик:**
- Requests per second: > 50 RPS
- Response time: p50 < 200ms, p95 < 500ms, p99 < 1000ms
- Failure rate: < 5%
- System resources: CPU < 80%, RAM < 85%

**Оптимизация по результатам:**
- Высокий response time: оптимизировать queries, добавить кэширование
- Высокий failure rate: улучшить error handling, retry логику
- Высокое CPU использование: оптимизировать FFmpeg, использовать hardware acceleration

---

## Подзадача 5.4: Документация

### Задачи реализации

**API usage examples в [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md):**

```markdown
# API Usage Examples

## Authentication

### Register New User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "id": 123,
  "username": "newuser",
  "email": "newuser@example.com",
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Task Examples

### Join Videos

```bash
curl -X POST http://localhost:8000/api/v1/tasks/join \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": [123, 124, 125],
    "output_filename": "joined_video.mp4"
  }'
```

### Complete Workflow Example

```bash
# 1. Регистрация
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "workflow_user",
    "email": "workflow@example.com",
    "password": "password123"
  }')

# 2. Логин
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email_or_username": "workflow@example.com",
    "password": "password123"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

# 3. Загрузка видео
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video1.mp4")

FILE_ID_1=$(echo $UPLOAD_RESPONSE | jq -r '.id')

# 4. Создание задачи на объединение
TASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/tasks/join \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_ids\": [$FILE_ID_1, $FILE_ID_2],
    \"output_filename\": \"joined.mp4\"
  }")

TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')

# 5. Проверка статуса задачи
sleep 5
STATUS_RESPONSE=$(curl -s -X GET http://localhost:8000/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN")

echo "Task status:"
echo $STATUS_RESPONSE | jq '.status, .progress, .result'
```

**Troubleshooting guide в [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md):**

```markdown
# Troubleshooting Guide

## Common Issues and Solutions

### 1. Docker Container Issues

#### Containers fail to start

**Problem:** Docker containers fail to start immediately

**Solutions:**
```bash
# Check container logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs api

# Check port conflicts
netstat -an | grep :5432  # PostgreSQL
netstat -an | grep :6379  # Redis
netstat -an | grep :8000  # API

# Stop conflicting services
sudo service postgresql stop  # Stop local PostgreSQL
sudo service redis-server stop  # Stop local Redis
```

### 2. Database Issues

#### Connection refused

**Problem:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### 3. FFmpeg Issues

#### FFmpeg not found

**Problem:** `FileNotFoundError: ffmpeg not found`

**Solutions:**
```bash
# Check FFmpeg installation
ffmpeg -version

# Install FFmpeg (Ubuntu/Debian)
sudo apt update
sudo apt install ffmpeg
```

#### Slow processing

**Problem:** Video processing is very slow

**Solutions:**
```bash
# Check FFmpeg threads
ffmpeg -threads 4 -i input.mp4 output.mp4

# Use hardware acceleration (NVIDIA)
ffmpeg -hwaccel cuda -i input.mp4 output.mp4

# Use hardware acceleration (Intel QSV)
ffmpeg -hwaccel qsv -i input.mp4 output.mp4
```

### 4. API Issues

#### 401 Unauthorized

**Problem:** API returns 401 Unauthorized

**Solutions:**
```bash
# Check token is valid
# Decode token: https://jwt.io/

# Refresh token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

## Emergency Procedures

### Reset database

```bash
# WARNING: This deletes all data
docker-compose down -v
docker-compose up -d
```
```

### Тестирование подзадачи 5.4

**Проверка документации:**
- OpenAPI docs доступны и полны: http://localhost:8000/docs
- API Examples содержат рабочие примеры
- Troubleshooting guide покрывает частые проблемы
- Deployment guide актуален
- Architecture docs актуальны

---

## Подзадача 5.5: Production deployment

### Задачи реализации

**Nginx конфигурация в [docker/nginx.conf](docker/nginx.conf):**

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=10r/m;

    # Upstream API server
    upstream api_server {
        server api:8000;
        keepalive 32;
    }

    # Main server
    server {
        listen 80;
        server_name api.example.com;

        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name api.example.com;

        # SSL certificates (Let's Encrypt)
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
        ssl_prefer_server_ciphers off;

        # HSTS
        add_header Strict-Transport-Security "max-age=31536000" always;

        # Gzip compression
        gzip on;
        gzip_vary on;
        gzip_proxied any;
        gzip_comp_level 6;
        gzip_types text/plain text/css text/xml text/javascript
                   application/json application/javascript application/xml+rss;

        # Proxy API requests
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://api_server;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Buffering
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
            proxy_busy_buffers_size 8k;
        }

        # Health check
        location /health {
            proxy_pass http://api_server/api/v1/health;
            access_log off;
        }
    }
}
```

**SSL сертификаты с Let's Encrypt:**

```bash
# Сертификаты в docker/nginx/ssl/

# Генерация сертификатов (только для тестирования)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/nginx/ssl/privkey.pem \
  -out docker/nginx/ssl/fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=api.example.com"

# Production сертификаты (Let's Encrypt)
# В production использовать certbot:

# 1. Сначала запустить nginx без SSL для domain validation
# 2. Получить сертификаты:
certbot certonly --webroot -w /var/www/html \
  -d api.example.com

# 3. Скопировать сертификаты в docker/nginx/ssl/
cp /etc/letsencrypt/live/api.example.com/fullchain.pem docker/nginx/ssl/
cp /etc/letsencrypt/live/api.example.com/privkey.pem docker/nginx/ssl/

# 4. Создать cron job для автоматического продления:
# 0 0,12 * * * certbot renew --quiet
```

**Production docker-compose в [docker-compose.prod.yml](docker-compose.prod.yml):**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: ffmpeg-postgres-prod
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data
    networks:
      - ffmpeg-network-prod
    restart: always

  redis:
    image: redis:7-alpine
    container_name: ffmpeg-redis-prod
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data_prod:/data
    networks:
      - ffmpeg-network-prod
    restart: always

  minio:
    image: minio/minio:latest
    container_name: ffmpeg-minio-prod
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data_prod:/data
    networks:
      - ffmpeg-network-prod
    restart: always

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: ffmpeg-api-prod
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      MINIO_BUCKET_NAME: ${MINIO_BUCKET_NAME}
      JWT_SECRET: ${JWT_SECRET}
      ENVIRONMENT: production
      LOG_LEVEL: INFO
      DEBUG: False
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    volumes:
      - ./app:/app/app
      - ./uploads_prod:/app/uploads
      - ./temp_prod:/app/temp
    depends_on:
      - postgres
      - redis
      - minio
    networks:
      - ffmpeg-network-prod
    restart: always

  nginx:
    image: nginx:alpine
    container_name: ffmpeg-nginx-prod
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx/ssl:/etc/nginx/ssl:ro
      - ./docker/nginx/.htpasswd:/etc/nginx/.htpasswd:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    networks:
      - ffmpeg-network-prod
    restart: always

networks:
  ffmpeg-network-prod:
    driver: bridge

volumes:
  postgres_data_prod:
  redis_data_prod:
  minio_data_prod:
```

**Production environment variables в [.env.production](.env.production):**

```bash
# Database
POSTGRES_DB=ffmpeg_api_prod
POSTGRES_USER=prod_user
POSTGRES_PASSWORD=<strong_password>
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=<optional_password>

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=<strong_password>
MINIO_BUCKET_NAME=ffmpeg-files-prod
MINIO_REGION=us-east-1

# JWT
JWT_SECRET=<very_long_secret_key_min_32_chars>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=False

# FFmpeg
FFMPEG_THREADS=4
FFMPEG_PRESET=medium

# Celery
CELERY_BROKER_URL=redis://password@redis:6379/0
CELERY_RESULT_BACKEND=redis://password@redis:6379/0
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=3600
CELERY_TASK_SOFT_TIME_LIMIT=3000

# Storage
STORAGE_RETENTION_DAYS=30
MAX_UPLOAD_SIZE=1073741824

# Monitoring
ENABLE_METRICS=True
GRAFANA_ADMIN_PASSWORD=<strong_password>

# Nginx
NGINX_RATE_LIMIT_API=60
NGINX_RATE_LIMIT_AUTH=10

# Domain
DOMAIN=api.example.com
```

**Backup скрипты в [scripts/](scripts/):**

*[scripts/backup.sh](scripts/backup.sh):*

```bash
#!/bin/bash

# Backup script for FFmpeg API
# Usage: ./scripts/backup.sh

set -e

# Configuration
BACKUP_DIR="/backups/ffmpeg-api"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_${DATE}"

# Create backup directory
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
docker exec ffmpeg-postgres-prod pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} \
  > "${BACKUP_DIR}/${BACKUP_NAME}/database.sql"

# Backup MinIO
echo "Backing up MinIO..."
mc mirror local/ffmpeg-files-prod "${BACKUP_DIR}/${BACKUP_NAME}/minio"

# Backup configuration
echo "Backing up configuration..."
cp .env.production "${BACKUP_DIR}/${BACKUP_NAME}/.env"
cp docker-compose.prod.yml "${BACKUP_DIR}/${BACKUP_NAME}/docker-compose.yml"

# Compress backup
echo "Compressing backup..."
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" -C "${BACKUP_DIR}" "${BACKUP_NAME}"

# Remove uncompressed backup
rm -rf "${BACKUP_DIR}/${BACKUP_NAME}"

# Keep last 30 backups
find "${BACKUP_DIR}" -name "backup_*.tar.gz" -mtime +30 -delete

echo "Backup complete: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
```

*[scripts/restore.sh](scripts/restore.sh):*

```bash
#!/bin/bash

# Restore script for FFmpeg API
# Usage: ./scripts/restore.sh <backup_name>

set -e

BACKUP_DIR="/backups/ffmpeg-api"
BACKUP_NAME=$1

if [ -z "$BACKUP_NAME" ]; then
  echo "Usage: $0 <backup_name>"
  echo "Example: $0 backup_20240101_120000"
  exit 1
fi

BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

# Extract backup
echo "Extracting backup..."
tar -xzf "$BACKUP_FILE" -C "$BACKUP_DIR"

# Stop services
echo "Stopping services..."
docker-compose -f docker-compose.prod.yml down

# Restore PostgreSQL
echo "Restoring PostgreSQL..."
docker run --rm \
  -v "${BACKUP_DIR}/${BACKUP_NAME}/database.sql:/backup.sql" \
  -v postgres_data_prod:/var/lib/postgresql/data \
  postgres:15-alpine \
  psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} < /backup.sql

# Restore MinIO
echo "Restoring MinIO..."
mc mirror "${BACKUP_DIR}/${BACKUP_NAME}/minio" local/ffmpeg-files-prod

# Restore configuration
echo "Restoring configuration..."
cp "${BACKUP_DIR}/${BACKUP_NAME}/.env" .env.production
cp "${BACKUP_DIR}/${BACKUP_NAME}/docker-compose.yml" docker-compose.prod.yml

# Start services
echo "Starting services..."
docker-compose -f docker-compose.prod.yml up -d

echo "Restore complete: $BACKUP_NAME"
```

### Тестирование подзадачи 5.5

**Развертывание production окружения:**

```bash
# Копировать production environment variables
cp .env.example .env.production
# Edit .env.production with production values

# Запуск production containers
docker-compose -f docker-compose.prod.yml up -d

# Проверка health checks
curl http://localhost/api/v1/health
curl https://api.example.com/api/v1/health

# Проверка SSL сертификатов
openssl s_client -connect api.example.com:443 -servername api.example.com
```

**Тестирование backup/restore:**

```bash
# Тест backup
./scripts/backup.sh

# Проверка что backup создан
ls -lh /backups/ffmpeg-api/

# Тест restore (на тестовой среде)
./scripts/restore.sh backup_20240101_120000

# Проверка что данные восстановлены
```

---

## Подзадача 5.6: CI/CD (опционально)

### Задачи реализации

**GitHub Actions workflow в [.github/workflows/ci.yml](.github/workflows/ci.yml):**

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run linting
      run: |
        black --check app/
        flake8 app/
        mypy app/
    
    - name: Run tests
      run: |
        pytest tests/ -m unit --cov=app --cov-report=xml --cov-fail-under=80
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Upload coverage artifacts
      uses: actions/upload-artifact@v3
      with:
        name: coverage-report
        path: htmlcov/

  build:
    needs: [test]
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Build Docker image
      run: |
        docker build -t ffmpeg-api:latest -f docker/Dockerfile.api .
    
    - name: Test Docker image
      run: |
        docker run --rm ffmpeg-api:latest python -m pytest tests/ -m unit
    
    - name: Login to Docker Hub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}
    
    - name: Push Docker image
      run: |
        docker push ffmpeg-api:latest
        docker tag ffmpeg-api:latest ffmpeg-api:${{ github.sha }}
        docker push ffmpeg-api:${{ github.sha }}
```

**GitHub Actions workflow для деплоя в [.github/workflows/deploy.yml](.github/workflows/deploy.yml):**

```yaml
name: Deploy

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Configure SSH
      run: |
        mkdir -p ~/.ssh
        echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
        chmod 600 ~/.ssh/id_rsa
        ssh-keyscan -H ${{ secrets.SERVER_HOST }} >> ~/.ssh/known_hosts
    
    - name: Deploy to server
      run: |
        ssh ${{ secrets.SERVER_USER }}@${{ secrets.SERVER_HOST }} << 'EOF'
          cd /path/to/ffmpeg-api
          git pull origin main
          ./scripts/deploy.sh
        EOF
    
    - name: Health check
      run: |
        sleep 60
        curl -f https://api.example.com/api/v1/health
    
    - name: Notify on success
      if: success()
        run: |
          echo "Deployment successful"
          # Add notification logic (Slack, email, etc.)
    
    - name: Notify on failure
      if: failure()
        run: |
          echo "Deployment failed"
          # Add notification logic (Slack, email, etc.)
```

**Deployment скрипты в [scripts/](scripts/):**

*[scripts/deploy.sh](scripts/deploy.sh):**

```bash
#!/bin/bash

# Deployment script for FFmpeg API
# Usage: ./scripts/deploy.sh <branch>

set -e

BRANCH=${1:-main}

echo "Deploying branch: $BRANCH"

# Pull latest code
echo "Pulling latest code..."
git fetch origin
git checkout origin/$BRANCH
git pull origin $BRANCH

# Build images
echo "Building Docker images..."
docker-compose -f docker-compose.prod.yml build

# Stop old containers
echo "Stopping old containers..."
docker-compose -f docker-compose.prod.yml down

# Start new containers
echo "Starting new containers..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Run migrations
echo "Running migrations..."
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head

# Health check
echo "Running health check..."
curl -f http://localhost/api/v1/health || exit 1

echo "Deployment complete!"
```

*[scripts/rollback.sh](scripts/rollback.sh):**

```bash
#!/bin/bash

# Rollback script for FFmpeg API
# Usage: ./scripts/rollback.sh

set -e

echo "Rolling back deployment..."

# Get previous commit
PREVIOUS_COMMIT=$(git log -2 --pretty=format:"%H" | tail -1)

echo "Rolling back to: $PREVIOUS_COMMIT"

# Checkout previous commit
git checkout $PREVIOUS_COMMIT

# Deploy previous version
./scripts/deploy.sh

echo "Rollback complete!"
```

### Тестирование подзадачи 5.6

**Тест CI workflow:**

```bash
# Push to trigger CI
git push origin feature/test-ci

# Check GitHub Actions
# https://github.com/username/ffmpeg-api/actions

# Verify:
# - Linting passes
# - Tests pass with coverage > 80%
# - Docker image builds
# - Image pushes to registry
```

**Тест Deploy workflow:**

```bash
# Manual trigger
# GitHub: Actions > Deploy > Run workflow

# Or push to main
git push origin main

# Verify:
# - Deployment succeeds
# - Health check passes
# - Notifications work
```

---

## Критерии завершения Этапа 5

**Функциональные требования:**
- Coverage > 80% по всему коду
- Все unit тесты проходят
- Все integration тесты проходят
- Все e2e тесты проходят
- Load тесты показывают приемлемую производительность
- Documentation полная и актуальная
- Production deployment работает
- CI/CD pipeline работает (опционально)

**Требования к тестированию:**
- Coverage > 80% (pytest --cov-fail-under=80)
- Все тесты в CI проходят
- Load tests: 100 concurrent requests
- Load tests: failure rate < 5%
- Load tests: p95 response time < 500ms

**Документация:**
- OpenAPI docs полны
- API Examples содержат рабочие примеры
- Troubleshooting guide покрывает частые проблемы
- Deployment guide актуален
- Architecture docs актуальны

**Production готовность:**
- Nginx настроен и работает
- SSL сертификаты валидны
- Backup скрипты работают
- Restore скрипты работают
- Health checks проходят
- Monitoring работает
- Alerts настроены
