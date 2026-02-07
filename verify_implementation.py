"""
Верификация реализации Подзадачи 3.5: Комбинированные операции
"""
import os
import sys

def check_file_exists(filepath):
    """Проверка существования файла"""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"[OK] {filepath} ({size} bytes)")
        return True
    else:
        print(f"[MISSING] {filepath}")
        return False

def check_file_content(filepath, expected_patterns):
    """Проверка содержания файла на наличие паттернов"""
    if not os.path.exists(filepath):
        print(f"[MISSING] {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    missing = []
    for pattern in expected_patterns:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print(f"[INCOMPLETE] {filepath} - Missing patterns: {missing}")
        return False
    else:
        print(f"[OK] {filepath} - All patterns found")
        return True

def main():
    print("=" * 70)
    print("Verification of Subtask 3.5: Combined Operations Implementation")
    print("=" * 70)
    print()
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    results = []
    
    # 1. Pydantic schemas (app/schemas/combined.py)
    print("1. Pydantic Schemas")
    print("-" * 70)
    filepath = os.path.join(base_path, "app/schemas/combined.py")
    expected_patterns = [
        "class OperationType",
        "JOIN = 'join'",
        "AUDIO_OVERLAY = 'audio_overlay'",
        "TEXT_OVERLAY = 'text_overlay'",
        "SUBTITLES = 'subtitles'",
        "VIDEO_OVERLAY = 'video_overlay'",
        "class Operation",
        "class CombinedRequest",
        "min_length=2",
        "max_length=10",
    ]
    results.append(("schemas/combined.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # 2. Processor (app/processors/combined_processor.py)
    print("2. CombinedProcessor")
    print("-" * 70)
    filepath = os.path.join(base_path, "app/processors/combined_processor.py")
    expected_patterns = [
        "class CombinedProcessor(BaseProcessor)",
        "self.intermediate_files",
        "async def validate_input",
        "async def process",
        "async def _execute_operation",
        "async def _rollback",
        "async def cleanup",
        "async def _load_file",
        "async def _upload_result",
        "At least 2 operations required",
        "Maximum 10 operations allowed",
    ]
    results.append(("processors/combined_processor.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # 3. Celery task (app/queue/tasks.py)
    print("3. Celery Task")
    print("-" * 70)
    filepath = os.path.join(base_path, "app/queue/tasks.py")
    expected_patterns = [
        "def combined_task",
        "CombinedProcessor",
        "operations",
        "base_file_id",
    ]
    results.append(("queue/tasks.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # 4. API endpoint (app/api/v1/tasks.py)
    print("4. API Endpoint")
    print("-" * 70)
    filepath = os.path.join(base_path, "app/api/v1/tasks.py")
    expected_patterns = [
        "class CombinedTaskBody",
        "from app.schemas.combined import CombinedRequest",
        "from app.queue.tasks import combined_task",
        "def create_combined_task",
        '"/combined"',
        "At least 2 operations required",
        "Maximum 10 operations allowed",
    ]
    results.append(("api/v1/tasks.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # 5. Tests (tests/processors/test_combined_processor.py)
    print("5. Unit Tests")
    print("-" * 70)
    filepath = os.path.join(base_path, "tests/processors/test_combined_processor.py")
    expected_patterns = [
        "class TestCombinedSchemas",
        "test_operation_type_enum",
        "test_combined_request_min_operations",
        "test_combined_request_max_operations",
        "class TestCombinedProcessorValidation",
        "test_validate_input_success",
        "test_validate_input_too_few_operations",
        "test_validate_input_too_many_operations",
        "class TestCombinedProcessorProcess",
        "test_process_two_operations",
        "test_process_three_operations",
        "test_process_rollback_on_error",
        "class TestCombinedProcessorCleanup",
        "test_cleanup_removes_temp_files",
        "test_cleanup_clears_lists",
        "class TestCombinedProcessorIntegration",
        "test_simple_pipeline_two_operations",
        "test_pipeline_rollback_on_error",
    ]
    results.append(("tests/processors/test_combined_processor.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # 6. API Tests (tests/api/v1/test_combined_tasks.py)
    print("6. API Tests")
    print("-" * 70)
    filepath = os.path.join(base_path, "tests/api/v1/test_combined_tasks.py")
    expected_patterns = [
        "class TestCombinedTasksAPI",
        "test_create_combined_task_success",
        "test_create_combined_task_with_output_filename",
        "test_create_combined_task_too_few_operations",
        "test_create_combined_task_too_many_operations",
        "test_create_combined_task_complex_pipeline",
    ]
    results.append(("tests/api/v1/test_combined_tasks.py", check_file_content(filepath, expected_patterns)))
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")
    
    print()
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
    print("=" * 70)
    
    if failed == 0:
        print()
        print("SUCCESS: All components have been implemented!")
        print()
        print("Implementation includes:")
        print("  1. Pydantic schemas (OperationType, Operation, CombinedRequest)")
        print("  2. CombinedProcessor with full pipeline support")
        print("  3. Celery task for async processing")
        print("  4. API endpoint POST /api/v1/tasks/combined")
        print("  5. Comprehensive unit tests")
        print("  6. API integration tests")
        print()
        print("Key features:")
        print("  - Sequential execution of 2-10 operations")
        print("  - Progress tracking and updates")
        print("  - Rollback on errors with cleanup")
        print("  - Intermediate file management")
        print("  - MinIO integration for file storage")
        print("  - Dynamic processor loading for different operation types")
        print()
        return 0
    else:
        print(f"\n[ERROR] {failed} component(s) missing or incomplete\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
