"""
Скрипт для проверки импортов и базового функционала CombinedProcessor
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_schemas_import():
    """Тест импорта schemas"""
    print("Testing schemas import...")
    try:
        from app.schemas.combined import OperationType, Operation, CombinedRequest
        print("✓ Schemas imported successfully")
        
        # Тест создания Operation
        op = Operation(
            type=OperationType.TEXT_OVERLAY,
            config={"text": "Hello"}
        )
        print(f"✓ Operation created: {op.type}")
        
        # Тест создания CombinedRequest
        request = CombinedRequest(
            operations=[
                Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"}),
                Operation(type=OperationType.AUDIO_OVERLAY, config={})
            ],
            base_file_id=1
        )
        print(f"✓ CombinedRequest created with {len(request.operations)} operations")
        
        return True
    except Exception as e:
        print(f"✗ Schemas import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processor_import():
    """Тест импорта процессора"""
    print("\nTesting processor import...")
    try:
        from app.processors.combined_processor import CombinedProcessor
        print("✓ CombinedProcessor imported successfully")
        
        # Тест создания процессора
        processor = CombinedProcessor(
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
        print(f"✓ CombinedProcessor created with {len(processor.config['operations'])} operations")
        print(f"✓ Intermediate files list: {processor.intermediate_files}")
        
        return True
    except Exception as e:
        print(f"✗ Processor import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_celery_task_import():
    """Тест импорта Celery задачи"""
    print("\nTesting Celery task import...")
    try:
        from app.queue.tasks import combined_task
        print("✓ combined_task imported successfully")
        print(f"✓ Task name: {combined_task.name}")
        
        return True
    except Exception as e:
        print(f"✗ Celery task import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_import():
    """Тест импорта API endpoint"""
    print("\nTesting API import...")
    try:
        from app.api.v1.tasks import create_combined_task, CombinedTaskBody
        print("✓ API endpoint imported successfully")
        
        # Тест создания тела запроса
        body = CombinedTaskBody(
            base_file_id=1,
            operations=[
                {"type": "text_overlay", "config": {"text": "Hello"}},
                {"type": "audio_overlay", "config": {}}
            ]
        )
        print(f"✓ CombinedTaskBody created with {len(body.operations)} operations")
        
        return True
    except Exception as e:
        print(f"✗ API import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schemas_validation():
    """Тест валидации schemas"""
    print("\nTesting schemas validation...")
    try:
        from app.schemas.combined import OperationType, Operation, CombinedRequest
        from pydantic import ValidationError
        
        # Тест валидации с недостаточным количеством операций
        try:
            request = CombinedRequest(
                operations=[
                    Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"})
                ],
                base_file_id=1
            )
            print("✗ Should have raised ValidationError for 1 operation")
            return False
        except ValidationError as e:
            print("✓ Correctly raised ValidationError for 1 operation")
        
        # Тест валидации с избыточным количеством операций
        try:
            request = CombinedRequest(
                operations=[
                    Operation(type=OperationType.TEXT_OVERLAY, config={"text": f"Text {i}"})
                    for i in range(11)
                ],
                base_file_id=1
            )
            print("✗ Should have raised ValidationError for 11 operations")
            return False
        except ValidationError as e:
            print("✓ Correctly raised ValidationError for 11 operations")
        
        # Тест валидации с допустимым количеством операций
        try:
            request = CombinedRequest(
                operations=[
                    Operation(type=OperationType.TEXT_OVERLAY, config={"text": "Hello"}),
                    Operation(type=OperationType.AUDIO_OVERLAY, config={})
                ],
                base_file_id=1
            )
            print(f"✓ Valid CombinedRequest with {len(request.operations)} operations")
        except ValidationError as e:
            print(f"✗ Unexpected ValidationError: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Schemas validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processor_validation():
    """Тест валидации процессора"""
    print("\nTesting processor validation...")
    try:
        from app.processors.combined_processor import CombinedProcessor
        from app.ffmpeg.exceptions import FFmpegValidationError
        import asyncio
        
        async def run_validation_tests():
            # Тест успешной валидации
            processor = CombinedProcessor(
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
            
            try:
                await processor.validate_input()
                print("✓ Valid config passed validation")
            except Exception as e:
                print(f"✗ Valid config failed validation: {e}")
                return False
            
            # Тест валидации с недостаточным количеством операций
            processor.config["operations"] = [
                {"type": "text_overlay", "config": {"text": "Hello"}}
            ]
            
            try:
                await processor.validate_input()
                print("✗ Should have raised FFmpegValidationError for 1 operation")
                return False
            except FFmpegValidationError as e:
                print("✓ Correctly raised FFmpegValidationError for 1 operation")
            
            # Тест валидации с избыточным количеством операций
            processor.config["operations"] = [
                {"type": "text_overlay", "config": {"text": f"Text {i}"}}
                for i in range(11)
            ]
            
            try:
                await processor.validate_input()
                print("✗ Should have raised FFmpegValidationError for 11 operations")
                return False
            except FFmpegValidationError as e:
                print("✓ Correctly raised FFmpegValidationError for 11 operations")
            
            # Тест валидации с недопустимым типом операции
            processor.config["operations"] = [
                {"type": "invalid_type", "config": {}},
                {"type": "text_overlay", "config": {"text": "Hello"}}
            ]
            
            try:
                await processor.validate_input()
                print("✗ Should have raised FFmpegValidationError for invalid operation type")
                return False
            except FFmpegValidationError as e:
                print("✓ Correctly raised FFmpegValidationError for invalid operation type")
            
            return True
        
        return asyncio.run(run_validation_tests())
    except Exception as e:
        print(f"✗ Processor validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("Combined Operations Implementation Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Schemas Import", test_schemas_import()))
    results.append(("Processor Import", test_processor_import()))
    results.append(("Celery Task Import", test_celery_task_import()))
    results.append(("API Import", test_api_import()))
    results.append(("Schemas Validation", test_schemas_validation()))
    results.append(("Processor Validation", test_processor_validation()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:30s} {status}")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed
    
    print("\n" + "=" * 60)
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
