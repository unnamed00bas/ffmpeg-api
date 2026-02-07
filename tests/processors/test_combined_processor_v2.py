"""
Unit tests for CombinedProcessor
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any

from app.processors.combined_processor import CombinedProcessor
from app.ffmpeg.exceptions import FFmpegValidationError


# Unit tests for schemas
class TestCombinedSchemas:
    """Тесты для Pydantic schemas комбинированных операций"""
    
    def test_operation_type_enum(self):
        """Тест перечисления OperationType"""
        from app.schemas.combined import OperationType
        
        assert OperationType.JOIN == "join"
        assert OperationType.AUDIO_OVERLAY == "audio_overlay"
        assert OperationType.TEXT_OVERLAY == "text_overlay"
        assert OperationType.SUBTITLES == "subtitles"
        assert OperationType.VIDEO_OVERLAY == "video_overlay"
    
    def test_operation_schema(self):
        """Тест схемы Operation"""
        from app.schemas.combined import Operation, OperationType
        
        op = Operation(
            type=OperationType.TEXT_OVERLAY,
            config={"text": "Hello", "position": "center"}
        )
        assert op.type == OperationType.TEXT_OVERLAY
        assert op.config == {"text": "Hello", "position": "center"}
    
    def test_operation_with_default_config(self):
        """Тест Operation с пустым config"""
        from app.schemas.combined import Operation, OperationType
        
        op = Operation(type=OperationType.AUDIO_OVERLAY)
        assert op.config == {}
    
    def test_combined_request_min_operations(self):
        """Тест CombinedRequest с минимальным количеством операций"""
        from app.schemas.combined import CombinedRequest, Operation, OperationType
        
        request = CombinedRequest(
            operations=[
                Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"}),
                Operation(type=OperationType.SUBTITLES, config={"format": "srt"})
            ],
            base_file_id=1
        )
        assert len(request.operations) == 2
        assert request.base_file_id == 1
    
    def test_combined_request_max_operations(self):
        """Тест CombinedRequest с максимальным количеством операций"""
        from app.schemas.combined import CombinedRequest, Operation, OperationType
        
        operations = [
            Operation(type=OperationType.TEXT_OVERLAY, config={"text": f"Text {i}"})
            for i in range(10)
        ]
        request = CombinedRequest(
            operations=operations,
            base_file_id=1
        )
        assert len(request.operations) == 10
    
    def test_combined_request_too_few_operations(self):
        """Тест CombinedRequest с недостаточным количеством операций"""
        from app.schemas.combined import CombinedRequest, Operation, OperationType
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            CombinedRequest(
                operations=[
                    Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"})
                ],
                base_file_id=1
            )
        assert "at least 2" in str(exc_info.value).lower()
    
    def test_combined_request_too_many_operations(self):
        """Тест CombinedRequest с избыточным количеством операций"""
        from app.schemas.combined import CombinedRequest, Operation, OperationType
        from pydantic import ValidationError
        
        operations = [
            Operation(type=OperationType.TEXT_OVERLAY, config={"text": f"Text {i}"})
            for i in range(11)
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            CombinedRequest(
                operations=operations,
                base_file_id=1
            )
        assert "at most 10" in str(exc_info.value).lower()
    
    def test_combined_request_with_output_filename(self):
        """Тест CombinedRequest с output_filename"""
        from app.schemas.combined import CombinedRequest, Operation, OperationType
        
        request = CombinedRequest(
            operations=[
                Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"}),
                Operation(type=OperationType.SUBTITLES, config={"format": "srt"})
            ],
            base_file_id=1,
            output_filename="result.mp4"
        )
        assert request.output_filename == "result.mp4"


# Unit tests for CombinedProcessor
class TestCombinedProcessorValidation:
    """Тесты валидации CombinedProcessor"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return CombinedProcessor(
            task_id=1,
            config={
                "operations": [
                    {"type": "text_overlay", "config": {"text": "Hello"}},
                    {"type": "audio_overlay", "config": {}}
                ],
                "base_file_id": 1
            },
            progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_validate_input_success(self, processor):
        """Тест успешной валидации"""
        # Не должно выбрасывать исключение
        await processor.validate_input()
    
    @pytest.mark.asyncio
    async def test_validate_input_too_few_operations(self, processor):
        """Тест валидации с 1 операцией"""
        processor.config["operations"] = [
            {"type": "text_overlay", "config": {"text": "Hello"}}
        ]
        
        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "at least 2" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_input_too_many_operations(self, processor):
        """Тест валидации с 11 операциями"""
        processor.config["operations"] = [
            {"type": "text_overlay", "config": {"text": f"Text {i}"}}
            for i in range(11)
        ]
        
        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "maximum 10" in str(exc_info.value).lower() or "at most 10" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_input_missing_base_file_id(self, processor):
        """Тест валидации без base_file_id"""
        processor.config["base_file_id"] = None
        
        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "base_file_id" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_input_invalid_operation_type(self, processor):
        """Тест валидации с недопустимым типом операции"""
        processor.config["operations"] = [
            {"type": "invalid_type", "config": {}},
            {"type": "text_overlay", "config": {"text": "Hello"}}
        ]
        
        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "invalid operation type" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_input_invalid_config_type(self, processor):
        """Тест валидации с некорректным типом config"""
        processor.config["operations"] = [
            {"type": "text_overlay", "config": "invalid"},
            {"type": "audio_overlay", "config": {}}
        ]
        
        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "dictionary" in str(exc_info.value).lower()


class TestCombinedProcessorProcess:
    """Тесты выполнения pipeline"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return CombinedProcessor(
            task_id=1,
            config={
                "operations": [
                    {"type": "text_overlay", "config": {"text": "Hello"}},
                    {"type": "audio_overlay", "config": {}}
                ],
                "base_file_id": 1,
                "user_id": 1,
                "output_filename": "combined.mp4"
            },
            progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_process_two_operations(self, processor):
        """Тест выполнения pipeline с 2 операциями"""
        progress_values = []
        processor.update_progress = lambda p: progress_values.append(p)
        
        # Мокирование _load_file, _execute_operation, _upload_result
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._execute_operation = AsyncMock(return_value="/tmp/output1.mp4")
        processor._upload_result = AsyncMock(return_value=123)
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            result = await processor.process()
        
        assert result["result_file_id"] == 123
        assert result["operations_count"] == 2
        assert len(progress_values) >= 2  # Прогресс для каждой операции + финальный
        assert 100.0 in progress_values
    
    @pytest.mark.asyncio
    async def test_process_three_operations(self, processor):
        """Тест выполнения pipeline с 3 операциями"""
        processor.config["operations"] = [
            {"type": "text_overlay", "config": {"text": "Hello"}},
            {"type": "audio_overlay", "config": {}},
            {"type": "subtitles", "config": {"format": "srt"}}
        ]
        
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._execute_operation = AsyncMock(side_effect=[
            "/tmp/output1.mp4",
            "/tmp/output2.mp4",
            "/tmp/output3.mp4"
        ])
        processor._upload_result = AsyncMock(return_value=456)
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            result = await processor.process()
        
        assert result["result_file_id"] == 456
        assert result["operations_count"] == 3
        assert processor._execute_operation.call_count == 3
    
    @pytest.mark.asyncio
    async def test_process_updates_progress(self, processor):
        """Тест корректного обновления прогресса"""
        progress_values = []
        processor.update_progress = lambda p: progress_values.append(p)
        
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._execute_operation = AsyncMock(return_value="/tmp/output.mp4")
        processor._upload_result = AsyncMock(return_value=789)
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await processor.process()
        
        # Проверка: прогресс обновляется для каждой операции
        assert len(progress_values) >= 2
        assert progress_values[-1] == 100.0
    
    @pytest.mark.asyncio
    async def test_process_rollback_on_error(self, processor):
        """Тест отката при ошибке в операции"""
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._execute_operation = AsyncMock(side_effect=Exception("Processing error"))
        processor._rollback = AsyncMock()
        
        with pytest.raises(Exception, match="Processing error"):
            await processor.process()
        
        processor._rollback.assert_called_once()


class TestCombinedProcessorExecuteOperation:
    """Тесты выполнения отдельных операций"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return CombinedProcessor(
            task_id=1,
            config={},
            progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_execute_operation_success(self, processor):
        """Тест успешного выполнения операции"""
        # Создание мок-процессора
        mock_processor = MagicMock()
        mock_processor.validate_input = AsyncMock()
        mock_processor.config = {}
        mock_processor.process = AsyncMock(return_value={
            "output_path": "/tmp/result.mp4"
        })
        
        processor._create_processor = AsyncMock(return_value=mock_processor)
        processor._prepare_processor_config = MagicMock()
        
        # Патчим os.path.exists для успешной проверки файла
        with patch("os.path.exists", return_value=True):
            operation = {
                "type": "text_overlay",
                "config": {"text": "Hello"}
            }
            
            result = await processor._execute_operation(operation, "/tmp/input.mp4")
        
        assert result == "/tmp/result.mp4"
        mock_processor.validate_input.assert_called_once()
        mock_processor.process.assert_called_once()
        assert "/tmp/result.mp4" in processor.intermediate_files
    
    @pytest.mark.asyncio
    async def test_execute_operation_adds_to_intermediate_files(self, processor):
        """Тест добавления файла в intermediate_files"""
        mock_processor = MagicMock()
        mock_processor.validate_input = AsyncMock()
        mock_processor.config = {}
        mock_processor.process = AsyncMock(return_value={
            "output_path": "/tmp/intermediate.mp4"
        })
        
        processor._create_processor = AsyncMock(return_value=mock_processor)
        processor._prepare_processor_config = MagicMock()
        
        with patch("os.path.exists", return_value=True):
            operation = {"type": "text_overlay", "config": {}}
            
            await processor._execute_operation(operation, "/tmp/input.mp4")
        
        assert "/tmp/intermediate.mp4" in processor.intermediate_files


class TestCombinedProcessorCleanup:
    """Тесты очистки временных файлов"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора с временными файлами"""
        p = CombinedProcessor(
            task_id=1,
            config={},
            progress_callback=None
        )
        p.temp_files = ["/tmp/temp1.mp4", "/tmp/temp2.mp4"]
        p.intermediate_files = ["/tmp/int1.mp4", "/tmp/int2.mp4"]
        return p
    
    @pytest.mark.asyncio
    async def test_cleanup_removes_temp_files(self, processor):
        """Тест удаления temp файлов"""
        with patch("os.path.exists", return_value=True), \
             patch("os.remove") as mock_remove:
            await processor.cleanup()
        
        assert len(processor.temp_files) == 0
        assert mock_remove.call_count >= 2  # temp + intermediate files
    
    @pytest.mark.asyncio
    async def test_cleanup_removes_intermediate_files(self, processor):
        """Тест удаления intermediate файлов"""
        with patch("os.path.exists", return_value=True), \
             patch("os.remove") as mock_remove:
            await processor.cleanup()
        
        assert len(processor.intermediate_files) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_clears_lists(self, processor):
        """Тест очистки списков файлов"""
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await processor.cleanup()
        
        assert processor.temp_files == []
        assert processor.intermediate_files == []
    
    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_files(self, processor):
        """Тест обработки отсутствующих файлов"""
        with patch("os.path.exists", return_value=False), \
             patch("os.remove") as mock_remove:
            await processor.cleanup()
        
        # os.remove не должен вызываться для несуществующих файлов
        assert mock_remove.call_count == 0


class TestCombinedProcessorRollback:
    """Тесты отката при ошибках"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return CombinedProcessor(
            task_id=1,
            config={},
            progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_rollback_calls_cleanup(self, processor):
        """Тест вызова cleanup при откате"""
        processor.cleanup = AsyncMock()
        
        await processor._rollback()
        
        processor.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_with_error_cleans_up(self, processor):
        """Тест очистки при ошибке в процессе"""
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._execute_operation = AsyncMock(side_effect=Exception("Error"))
        processor._upload_result = AsyncMock()  # Mock to avoid import error
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            try:
                await processor.process()
            except Exception as e:
                if str(e) != "Error":
                    raise
        
        # Все временные файлы должны быть удалены
        assert len(processor.temp_files) == 0
        assert len(processor.intermediate_files) == 0


class TestCombinedProcessorHelperMethods:
    """Тесты вспомогательных методов"""
    
    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return CombinedProcessor(
            task_id=1,
            config={},
            progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_extract_output_file_output_path(self, processor):
        """Тест извлечения output_path из результата"""
        result = {"output_path": "/tmp/output.mp4"}
        
        with patch("os.path.exists", return_value=True):
            path = processor._extract_output_file(result, "text_overlay")
            assert path == "/tmp/output.mp4"
    
    @pytest.mark.asyncio
    async def test_extract_output_file_output_file(self, processor):
        """Тест извлечения output_file из результата"""
        result = {"output_file": "/tmp/output.mp4"}
        
        with patch("os.path.exists", return_value=True):
            path = processor._extract_output_file(result, "audio_overlay")
            assert path == "/tmp/output.mp4"
    
    @pytest.mark.asyncio
    async def test_extract_output_file_not_found(self, processor):
        """Тест ошибки при отсутствии выходного файла"""
        result = {}
        
        with patch("os.path.exists", return_value=True):
            with pytest.raises(FFmpegValidationError) as exc_info:
                processor._extract_output_file(result, "text_overlay")
            assert "did not return a valid output file" in str(exc_info.value).lower()
    
    def test_prepare_processor_config_audio_overlay(self, processor):
        """Тест подготовки конфигурации для audio_overlay"""
        mock_processor = MagicMock()
        mock_processor.config = {}
        op_config = {"audio_file_id": 2}
        input_file = "/tmp/input.mp4"
        
        processor._prepare_processor_config(
            mock_processor, "audio_overlay", op_config, input_file
        )
        
        assert op_config["video_file_path"] == "/tmp/input.mp4"
    
    def test_prepare_processor_config_text_overlay(self, processor):
        """Тест подготовки конфигурации для text_overlay"""
        mock_processor = MagicMock()
        mock_processor.config = {}
        op_config = {"text": "Hello"}
        input_file = "/tmp/input.mp4"
        
        processor._prepare_processor_config(
            mock_processor, "text_overlay", op_config, input_file
        )
        
        assert op_config["video_file_path"] == "/tmp/input.mp4"
    
    def test_prepare_processor_config_subtitles(self, processor):
        """Тест подготовки конфигурации для subtitles"""
        mock_processor = MagicMock()
        mock_processor.config = {}
        op_config = {"format": "srt"}
        input_file = "/tmp/input.mp4"
        
        processor._prepare_processor_config(
            mock_processor, "subtitles", op_config, input_file
        )
        
        assert op_config["video_file_path"] == "/tmp/input.mp4"
    
    def test_prepare_processor_config_video_overlay(self, processor):
        """Тест подготовки конфигурации для video_overlay"""
        mock_processor = MagicMock()
        mock_processor.config = {}
        op_config = {"overlay_video_id": 3}
        input_file = "/tmp/input.mp4"
        
        processor._prepare_processor_config(
            mock_processor, "video_overlay", op_config, input_file
        )
        
        assert op_config["base_video_path"] == "/tmp/input.mp4"


# Integration tests
class TestCombinedProcessorIntegration:
    """Интеграционные тесты для CombinedProcessor"""
    
    @pytest.mark.asyncio
    async def test_simple_pipeline_two_operations(self):
        """Тест простого pipeline с 2 операциями"""
        processor = CombinedProcessor(
            task_id=1,
            config={
                "operations": [
                    {"type": "text_overlay", "config": {"text": "Hello"}},
                    {"type": "audio_overlay", "config": {}}
                ],
                "base_file_id": 1,
                "user_id": 1
            },
            progress_callback=None
        )
        
        # Мокирование внешних зависимостей
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._upload_result = AsyncMock(return_value=100)
        
        # Мокирование выполнения операций
        call_count = [0]
        async def mock_execute_op(operation, input_file):
            call_count[0] += 1
            return f"/tmp/output{call_count[0]}.mp4"
        
        processor._execute_operation = mock_execute_op
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            result = await processor.process()
        
        assert result["operations_count"] == 2
        assert result["result_file_id"] == 100
        assert call_count[0] == 2
    
    @pytest.mark.asyncio
    async def test_complex_pipeline_five_operations(self):
        """Тест сложного pipeline с 5 операциями"""
        processor = CombinedProcessor(
            task_id=2,
            config={
                "operations": [
                    {"type": "text_overlay", "config": {"text": "Text1"}},
                    {"type": "audio_overlay", "config": {}},
                    {"type": "subtitles", "config": {"format": "srt"}},
                    {"type": "text_overlay", "config": {"text": "Text2"}},
                    {"type": "video_overlay", "config": {}}
                ],
                "base_file_id": 1,
                "user_id": 1
            },
            progress_callback=None
        )
        
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        processor._upload_result = AsyncMock(return_value=200)
        
        call_count = [0]
        async def mock_execute_op(operation, input_file):
            call_count[0] += 1
            return f"/tmp/output{call_count[0]}.mp4"
        
        processor._execute_operation = mock_execute_op
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            result = await processor.process()
        
        assert result["operations_count"] == 5
        assert call_count[0] == 5  # 5 операций
    
    @pytest.mark.asyncio
    async def test_pipeline_rollback_on_error(self):
        """Тест отката при ошибке в середине pipeline"""
        processor = CombinedProcessor(
            task_id=3,
            config={
                "operations": [
                    {"type": "text_overlay", "config": {"text": "Text1"}},
                    {"type": "audio_overlay", "config": {}},
                    {"type": "subtitles", "config": {"format": "srt"}}
                ],
                "base_file_id": 1,
                "user_id": 1
            },
            progress_callback=None
        )
        
        processor._load_file = AsyncMock(return_value="/tmp/input.mp4")
        
        call_count = [0]
        async def mock_execute_op(operation, input_file):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Error in operation 2")
            return f"/tmp/output{call_count[0]}.mp4"
        
        processor._execute_operation = mock_execute_op
        
        with patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            with pytest.raises(Exception, match="Error in operation 2"):
                await processor.process()
        
        # Проверка очистки при ошибке
        assert len(processor.temp_files) == 0
        assert len(processor.intermediate_files) == 0
