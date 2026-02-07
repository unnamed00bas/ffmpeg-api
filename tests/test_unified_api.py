
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.v1.tasks import _resolve_file_id
from app.queue.tasks import ensure_file_local
from app.schemas.common import FileSource
from app.database.models.file import File

@pytest.mark.asyncio
async def test_resolve_file_id_int():
    service = AsyncMock()
    fid = await _resolve_file_id(123, 1, service)
    assert fid == 123
    service.register_remote_file.assert_not_called()

@pytest.mark.asyncio
async def test_resolve_file_id_url():
    service = AsyncMock()
    file_mock = MagicMock()
    file_mock.id = 456
    service.register_remote_file.return_value = file_mock
    
    url = "https://example.com/video.mp4"
    fid = await _resolve_file_id(url, 1, service)
    
    assert fid == 456
    service.register_remote_file.assert_called_once_with(1, url)

@patch("app.queue.tasks.httpx.Client")
def test_ensure_file_local_remote(mock_client_cls):
    # Mock DB
    db = MagicMock()
    file_record = File(id=1, user_id=1, storage_path="https://example.com/video.mp4", 
                       file_metadata={"is_remote": True}, original_filename="video.mp4")
    db.query().filter().first.return_value = file_record
    
    # Mock httpx
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.get.return_value.content = b"fake_content"
    mock_client.get.return_value.raise_for_status = MagicMock()
    
    # Mock MinIO
    storage = MagicMock()
    
    # Run
    result = ensure_file_local(db, 1, 1, storage)
    
    # Assert
    assert result.storage_path.startswith("1/")
    assert "video.mp4" in result.storage_path
    assert result.size == len(b"fake_content")
    assert result.file_metadata["is_remote"] is False
    storage.client.put_object.assert_called_once()

@patch("app.queue.tasks.ensure_file_local")
@patch("app.queue.tasks.get_db_sync")
@patch("app.queue.tasks.MinIOClient")
@patch("app.queue.tasks.CombinedProcessor")
@patch("app.queue.tasks.create_temp_dir")
@patch("app.queue.tasks.os.path.exists") # mock exists for cleanup
@patch("app.queue.tasks.os.remove") # mock remove for cleanup
@patch("app.queue.tasks.shutil.rmtree") # mock rmtree for cleanup
def test_combined_task_join_logic(mock_rmtree, mock_remove, mock_exists, mock_temp_dir, mock_processor_cls, mock_minio, mock_db_getter, mock_ensure):
    from app.queue.tasks import combined_task, Task, TaskStatus
    
    # Setup mocks
    db = MagicMock()
    mock_db_getter.return_value = db
    task_mock = Task(id=1, user_id=1, status=TaskStatus.PENDING)
    db.query().filter().first.return_value = task_mock
    
    mock_temp_dir.return_value = "/tmp/fake_dir"
    mock_exists.return_value = True # ensure cleanup tries to remove things
    
    # Mock ensure_file_local to return a value that allows fget_object to be called
    file_rec = MagicMock()
    file_rec.storage_path = "minio/path"
    file_rec.original_filename = "vid.mp4"
    mock_ensure.return_value = file_rec
    
    # Mock Processor
    processor_instance = AsyncMock()
    processor_instance.run.return_value = {"result_file_id": 999}
    mock_processor_cls.return_value = processor_instance
    
    # Config with JOIN and file_ids
    config = {
        "base_file_id": 10,
        "operations": [
            {
                "type": "join",
                "config": {"file_ids": [11, 12]}
            }
        ],
        "output_filename": "out.mp4"
    }
    
    # Run task
    res = combined_task(1, config)
    
    # Assert
    assert res["status"] == "completed"
    assert res["result_file_id"] == 999
    
    # Verify ensure_file_local called for base file AND join files
    # args: (db, file_id, user_id, storage)
    # Call 1: base file (10)
    # Call 2: join file 1 (11)
    # Call 3: join file 2 (12)
    assert mock_ensure.call_count >= 3
    call_args_list = mock_ensure.call_args_list
    assert call_args_list[0][0][1] == 10 # base
    assert call_args_list[1][0][1] == 11 # join 1
    assert call_args_list[2][0][1] == 12 # join 2
    
    # Verify processor created with updated config
    processor_args = mock_processor_cls.call_args[1]
    op_config = processor_args["config"]["operations"][0]["config"]
    assert "secondary_input_paths" in op_config
    assert len(op_config["secondary_input_paths"]) == 2
