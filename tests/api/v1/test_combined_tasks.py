"""
API tests for combined tasks endpoint
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.tasks import create_combined_task, router
from app.schemas.combined import CombinedRequest
from app.database.models.task import Task, TaskType, TaskStatus
from app.database.models.file import File


class TestCombinedTasksAPI:
    """API тесты для комбинированных операций"""
    
    @pytest.fixture
    def current_user(self):
        """Мок текущего пользователя"""
        user = MagicMock()
        user.id = 1
        return user
    
    @pytest.fixture
    def file_service(self, db_session: AsyncSession):
        """Мок сервиса файлов"""
        service = MagicMock()
        return service
    
    @pytest.fixture
    def task_service(self, db_session: AsyncSession):
        """Мок сервиса задач"""
        service = MagicMock()
        return service
    
    @pytest.fixture
    def base_file(self):
        """Мок базового файла"""
        file = MagicMock()
        file.id = 1
        file.user_id = 1
        file.original_filename = "input.mp4"
        file.storage_path = "1/input.mp4"
        file.size = 1024
        return file
    
    @pytest.fixture
    def task(self):
        """Мок задачи"""
        task = MagicMock()
        task.id = 1
        task.user_id = 1
        task.type = TaskType.COMBINED
        task.status = TaskStatus.PENDING
        task.input_files = [1]
        task.output_files = []
        task.config = {}
        task.error_message = None
        task.progress = 0.0
        task.result = None
        task.retry_count = 0
        task.priority = 5
        return task
    
    @pytest.mark.asyncio
    async def test_create_combined_task_success(
        self,
        current_user,
        task_service,
        file_service,
        base_file,
        task
    ):
        """Тест успешного создания комбинированной задачи"""
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ]
        )
        
        file_service.get_file_info = AsyncMock(return_value=base_file)
        task_service.create_task = AsyncMock(return_value=task)
        task_service._task_to_response = MagicMock(return_value={"id": 1, "type": "combined"})
        
        with patch("app.api.v1.tasks.combined_task") as mock_celery_task:
            mock_celery_task.delay = MagicMock()
            
            result = await create_combined_task(
                body=body,
                current_user=current_user,
                service=task_service,
                file_service=file_service
            )
        
        # Проверка создания задачи
        task_service.create_task.assert_called_once()
        assert task_service.create_task.call_args[1]["task_type"] == TaskType.COMBINED
        assert task_service.create_task.call_args[1]["input_files"] == [1]
        
        # Проверка запуска Celery задачи
        mock_celery_task.delay.assert_called_once()
        assert mock_celery_task.delay.call_args[0][0] == 1  # task_id
    
    @pytest.mark.asyncio
    async def test_create_combined_task_with_output_filename(
        self,
        current_user,
        task_service,
        file_service,
        base_file,
        task
    ):
        """Тест создания задачи с указанием output_filename"""
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ],
            output_filename="custom_output.mp4"
        )
        
        file_service.get_file_info = AsyncMock(return_value=base_file)
        task_service.create_task = AsyncMock(return_value=task)
        task_service._task_to_response = MagicMock(return_value={"id": 1})
        
        with patch("app.api.v1.tasks.combined_task") as mock_celery_task:
            mock_celery_task.delay = MagicMock()
            
            await create_combined_task(
                body=body,
                current_user=current_user,
                service=task_service,
                file_service=file_service
            )
        
        # Проверка, что output_filename включен в конфигурацию
        config_arg = task_service.create_task.call_args[1]["config"]
        assert config_arg["output_filename"] == "custom_output.mp4"
    
    @pytest.mark.asyncio
    async def test_create_combined_task_too_few_operations(
        self,
        current_user,
        file_service,
        base_file
    ):
        """Тест создания задачи с недостаточным количеством операций"""
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}}
            ]
        )
        
        file_service.get_file_info = AsyncMock(return_value=base_file)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await create_combined_task(
                body=body,
                current_user=current_user,
                service=MagicMock(),
                file_service=file_service
            )
        
        assert exc_info.value.status_code == 422
        assert "at least 2" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_create_combined_task_too_many_operations(
        self,
        current_user,
        file_service,
        base_file
    ):
        """Тест создания задачи с избыточным количеством операций"""
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": f"Text {i}"}}
                for i in range(11)
            ]
        )
        
        file_service.get_file_info = AsyncMock(return_value=base_file)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await create_combined_task(
                body=body,
                current_user=current_user,
                service=MagicMock(),
                file_service=file_service
            )
        
        assert exc_info.value.status_code == 422
        assert "maximum 10" in str(exc_info.value.detail).lower() or "at most 10" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_create_combined_task_base_file_not_found(
        self,
        current_user,
        file_service
    ):
        """Тест создания задачи с несуществующим base_file"""
        body = CombinedTaskBody(
            base_file_id=999,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ]
        )
        
        file_service.get_file_info = AsyncMock(return_value=None)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await create_combined_task(
                body=body,
                current_user=current_user,
                service=MagicMock(),
                file_service=file_service
            )
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_create_combined_task_complex_pipeline(
        self,
        current_user,
        task_service,
        file_service,
        base_file,
        task
    ):
        """Тест создания сложного pipeline"""
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Title"}},
                {"type": "audio_overlay", "config": {"mode": "mix"}},
                {"type": "subtitles", "config": {"format": "srt"}},
                {"type": "video_overlay", "config": {"scale": 0.3}},
                {"type": "text_overlay", "config": {"text": "Credits"}}
            ]
        )
        
        file_service.get_file_info = AsyncMock(return_value=base_file)
        task_service.create_task = AsyncMock(return_value=task)
        task_service._task_to_response = MagicMock(return_value={"id": 1})
        
        with patch("app.api.v1.tasks.combined_task") as mock_celery_task:
            mock_celery_task.delay = MagicMock()
            
            result = await create_combined_task(
                body=body,
                current_user=current_user,
                service=task_service,
                file_service=file_service
            )
        
        assert len(body.operations) == 5
        mock_celery_task.delay.assert_called_once()


class TestCombinedTasksSchema:
    """Тесты схемы CombinedTaskBody"""
    
    def test_combined_task_body_schema(self):
        """Тест схемы CombinedTaskBody"""
        from app.api.v1.tasks import CombinedTaskBody
        
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ]
        )
        
        assert body.base_file_id == 1
        assert len(body.operations) == 2
        assert body.output_filename is None
    
    def test_combined_task_body_with_output_filename(self):
        """Тест CombinedTaskBody с output_filename"""
        from app.api.v1.tasks import CombinedTaskBody
        
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ],
            output_filename="result.mp4"
        )
        
        assert body.output_filename == "result.mp4"
    
    def test_combined_task_body_operations_types(self):
        """Тест различных типов операций"""
        from app.api.v1.tasks import CombinedTaskBody
        
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "join", "config": {}},
                {"type": "audio_overlay", "config": {}},
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "subtitles", "config": {"format": "vtt"}},
                {"type": "video_overlay", "config": {"x": 10, "y": 10}}
            ]
        )
        
        assert len(body.operations) == 5
        ops = [op["type"] for op in body.operations]
        assert "join" in ops
        assert "audio_overlay" in ops
        assert "text_overlay" in ops
        assert "subtitles" in ops
        assert "video_overlay" in ops
