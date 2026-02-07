"""
Celery tasks for video processing
"""
import asyncio
import uuid
import asyncio
import uuid
from typing import Any, Dict, List
import httpx
import io
import os
from app.storage.minio_client import MinIOClient

from sqlalchemy.orm import Session

from app.database.connection import get_db_sync
from app.database.models.file import File
from app.database.models.task import Task, TaskStatus, TaskType
from app.queue.celery_app import celery_app
from app.config import get_settings


class TemporaryError(Exception):
    """Временная ошибка (сеть, MinIO), можно повторить задачу."""


class PermanentError(Exception):
    """Постоянная ошибка (валидация, данные), повтор бесполезен."""


def ensure_file_local(db: Session, file_id: int, user_id: int, storage: MinIOClient) -> File:
    """
    Ensure file is available in MinIO.
    If it's a remote file (URL), download it, upload to MinIO, and update DB.
    """
    file_record = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
    if not file_record or file_record.is_deleted:
        raise PermanentError(f"File {file_id} not found or deleted")
    
    # Check if metadata indicates remote file
    # Note: accessing file_metadata causing potential load if deferred?
    # SQLAlchemy default load should be fine.
    metadata = file_record.file_metadata or {}
    if metadata.get("is_remote"):
        # It's a remote URL
        url = file_record.storage_path
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content = resp.content
        except Exception as e:
            raise PermanentError(f"Failed to download remote file {url}: {e}")
        
        # Upload to MinIO
        object_name = f"{user_id}/{uuid.uuid4().hex}_{file_record.original_filename}"
        
        storage.client.put_object(
            storage.bucket_name,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type=file_record.content_type or "application/octet-stream"
        )
        
        # Update DB
        file_record.storage_path = object_name
        file_record.size = len(content)
        metadata["is_remote"] = False
        file_record.file_metadata = metadata
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
    return file_record


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def join_video_task(self, task_id: int, config: dict) -> dict:
    """
    Celery-задача объединения видео: скачать из MinIO -> VideoJoiner -> загрузить результат.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        input_file_ids = task.input_files if isinstance(task.input_files, list) else []
        if len(input_file_ids) < 2:
            task.status = TaskStatus.FAILED
            task.error_message = "At least 2 input files required"
            db.commit()
            raise PermanentError("At least 2 input files required")

        # Скачать файлы из MinIO во временную директорию
        from app.utils.temp_files import create_temp_dir, create_temp_file
        from app.storage.minio_client import MinIOClient
        import os

        storage = MinIOClient()
        temp_dir = create_temp_dir()
        local_paths: List[str] = []
        try:
            for fid in input_file_ids:
                # Ensure file is local (download if remote)
                file_record = ensure_file_local(db, fid, task.user_id, storage)
                
                local_path = os.path.join(temp_dir, f"{fid}_{file_record.original_filename}")
                storage.client.fget_object(storage.bucket_name, file_record.storage_path, local_path)
                local_paths.append(local_path)

            output_path = os.path.join(temp_dir, f"joined_{uuid.uuid4().hex}.mp4")
            joiner_config = {
                "input_paths": local_paths,
                "output_path": output_path,
                "timeout": getattr(settings, "TASK_TIMEOUT", 3600),
            }

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.video_joiner import VideoJoiner

            joiner = VideoJoiner(task_id=task_id, config=joiner_config, progress_callback=progress_cb)
            result = asyncio.run(joiner.run())

            out_path = result.get("output_path")
            if not out_path or not os.path.isfile(out_path):
                raise PermanentError("Join produced no output file")

            # Загрузить результат в MinIO и создать запись File
            object_name = f"{task.user_id}/joined_{uuid.uuid4().hex}.mp4"
            storage.client.fput_object(
                storage.bucket_name,
                object_name,
                out_path,
                content_type="video/mp4",
            )
            size = os.path.getsize(out_path)
            new_file = File(
                user_id=task.user_id,
                filename=object_name,
                original_filename=config.get("output_filename", "joined.mp4"),
                size=size,
                content_type="video/mp4",
                storage_path=object_name,
            )
            db.add(new_file)
            db.flush()

            output_files = list(task.output_files) if isinstance(task.output_files, list) else []
            output_files.append(new_file.id)
            task.output_files = output_files
            task.result = {"output_file_id": new_file.id, "object_name": object_name}
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            db.commit()
            return {"output_file_id": new_file.id, "status": "completed"}
        finally:
            for p in local_paths:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            try:
                if os.path.isdir(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def audio_overlay_task(self, task_id: int, config: dict) -> dict:
    """
    Celery-задача наложения аудио: скачать из MinIO -> AudioOverlay -> загрузить результат.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        input_file_ids = task.input_files if isinstance(task.input_files, list) else []
        if len(input_file_ids) != 2:
            task.status = TaskStatus.FAILED
            task.error_message = "Exactly 2 input files required (video and audio)"
            db.commit()
            raise PermanentError("Exactly 2 input files required (video and audio)")

        # Скачать файлы из MinIO во временную директорию
        from app.utils.temp_files import create_temp_dir
        from app.storage.minio_client import MinIOClient
        import os

        storage = MinIOClient()
        temp_dir = create_temp_dir()
        local_paths: List[str] = []
        try:
            # Первый файл - видео
            video_file_id = input_file_ids[0]
            video_file = ensure_file_local(db, video_file_id, task.user_id, storage)
            video_path = os.path.join(temp_dir, f"{video_file_id}_{video_file.original_filename}")
            storage.client.fget_object(storage.bucket_name, video_file.storage_path, video_path)
            local_paths.append(video_path)

            # Второй файл - аудио
            audio_file_id = input_file_ids[1]
            audio_file = ensure_file_local(db, audio_file_id, task.user_id, storage)
            audio_path = os.path.join(temp_dir, f"{audio_file_id}_{audio_file.original_filename}")
            storage.client.fget_object(storage.bucket_name, audio_file.storage_path, audio_path)
            local_paths.append(audio_path)

            output_path = os.path.join(temp_dir, f"audio_overlay_{uuid.uuid4().hex}.mp4")
            overlay_config = {
                "video_path": video_path,
                "audio_path": audio_path,
                "output_path": output_path,
                "mode": config.get("mode", "replace"),
                "offset": config.get("offset", 0.0),
                "duration": config.get("duration"),
                "original_volume": config.get("original_volume", 1.0),
                "overlay_volume": config.get("overlay_volume", 1.0),
                "timeout": getattr(settings, "TASK_TIMEOUT", 3600),
            }

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.audio_overlay import AudioOverlay

            overlay = AudioOverlay(task_id=task_id, config=overlay_config, progress_callback=progress_cb)
            result = asyncio.run(overlay.run())

            out_path = result.get("output_path")
            if not out_path or not os.path.isfile(out_path):
                raise PermanentError("Audio overlay produced no output file")

            # Загрузить результат в MinIO и создать запись File
            object_name = f"{task.user_id}/audio_overlay_{uuid.uuid4().hex}.mp4"
            storage.client.fput_object(
                storage.bucket_name,
                object_name,
                out_path,
                content_type="video/mp4",
            )
            size = os.path.getsize(out_path)
            new_file = File(
                user_id=task.user_id,
                filename=object_name,
                original_filename=config.get("output_filename", "audio_overlay.mp4"),
                size=size,
                content_type="video/mp4",
                storage_path=object_name,
            )
            db.add(new_file)
            db.flush()

            output_files = list(task.output_files) if isinstance(task.output_files, list) else []
            output_files.append(new_file.id)
            task.output_files = output_files
            task.result = {"output_file_id": new_file.id, "object_name": object_name}
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            db.commit()
            return {"output_file_id": new_file.id, "status": "completed"}
        finally:
            for p in local_paths:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            try:
                if os.path.isdir(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def video_overlay_task(self, task_id: int, config: dict) -> dict:
    """
    Celery-задача для picture-in-picture (video overlay).
    Скачать из MinIO -> VideoOverlay -> загрузить результат.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        base_file_id = config.get("base_video_file_id")
        overlay_file_id = config.get("overlay_video_file_id")

        if not base_file_id or not overlay_file_id:
            task.status = TaskStatus.FAILED
            task.error_message = "base_video_file_id and overlay_video_file_id are required"
            db.commit()
            raise PermanentError("base_video_file_id and overlay_video_file_id are required")

        # Скачать файлы из MinIO во временную директорию
        from app.utils.temp_files import create_temp_dir, create_temp_file
        from app.storage.minio_client import MinIOClient
        import os

        storage = MinIOClient()
        temp_dir = create_temp_dir()

        local_paths = {}
        try:
            # Download base video
            base_file = ensure_file_local(db, base_file_id, task.user_id, storage)
            base_local_path = os.path.join(temp_dir, f"{base_file_id}_base_{base_file.original_filename}")
            storage.client.fget_object(storage.bucket_name, base_file.storage_path, base_local_path)
            local_paths["base"] = base_local_path

            # Download overlay video
            overlay_file = ensure_file_local(db, overlay_file_id, task.user_id, storage)
            overlay_local_path = os.path.join(temp_dir, f"{overlay_file_id}_overlay_{overlay_file.original_filename}")
            storage.client.fget_object(storage.bucket_name, overlay_file.storage_path, overlay_local_path)
            local_paths["overlay"] = overlay_local_path

            # Generate output filename
            output_filename = config.get("output_filename", "overlay.mp4")
            output_path = os.path.join(temp_dir, f"overlay_{uuid.uuid4().hex}.mp4")

            # Prepare processor config
            processor_config = config.copy()
            processor_config["base_file_path"] = base_local_path
            processor_config["overlay_file_path"] = overlay_local_path
            processor_config["output_path"] = output_path
            processor_config["timeout"] = getattr(settings, "TASK_TIMEOUT", 3600)

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.video_overlay import VideoOverlay

            processor = VideoOverlay(task_id=task_id, config=processor_config, progress_callback=progress_cb)
            result = asyncio.run(processor.run())

            out_path = result.get("output_path")
            if not out_path or not os.path.isfile(out_path):
                raise PermanentError("Overlay produced no output file")

            # Upload result to MinIO and create File record
            object_name = f"{task.user_id}/overlay_{uuid.uuid4().hex}.mp4"
            storage.client.fput_object(
                storage.bucket_name,
                object_name,
                out_path,
                content_type="video/mp4",
            )
            size = os.path.getsize(out_path)
            new_file = File(
                user_id=task.user_id,
                filename=object_name,
                original_filename=output_filename,
                size=size,
                content_type="video/mp4",
                storage_path=object_name,
            )
            db.add(new_file)
            db.flush()

            output_files = list(task.output_files) if isinstance(task.output_files, list) else []
            output_files.append(new_file.id)
            task.output_files = output_files
            task.result = {"output_file_id": new_file.id, "object_name": object_name}
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            db.commit()
            return {"output_file_id": new_file.id, "status": "completed"}
        finally:
            # Cleanup temp files
            for path in local_paths.values():
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
            try:
                if os.path.isdir(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def combined_task(self, task_id: int, config: dict) -> dict:
    """
    Celery задача для комбинированных операций.
    Выполняет pipeline из нескольких операций последовательно.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        # Проверка base_file_id
        base_file_id = config.get("base_file_id")
        if not base_file_id:
            task.status = TaskStatus.FAILED
            task.error_message = "base_file_id is required"
            db.commit()
            raise PermanentError("base_file_id is required")
        
        # Initialize storage
        from app.storage.minio_client import MinIOClient
        storage = MinIOClient()
        
        # Prepare temp dir for auxiliary files
        from app.utils.temp_files import create_temp_dir
        import os
        
        temp_dir = create_temp_dir()
        local_resource_paths = []

        try:
            # Ensure base file is local
            ensure_file_local(db, base_file_id, task.user_id, storage)
            
            # Resolve and download files for operations
            operations = config.get("operations", [])
            operations_config = [] # Deep copy to avoid mutating original config if needed, or just iterate

            for op in operations:
                op_type = op.get("type")
                op_cfg = op.get("config", {})
                
                # Check for file IDs and download if present
                if op_type == "join" and "file_ids" in op_cfg:
                    secondary_paths = []
                    for fid in op_cfg["file_ids"]:
                        f_rec = ensure_file_local(db, fid, task.user_id, storage)
                        local_path = os.path.join(temp_dir, f"{fid}_join_{f_rec.original_filename}")
                        storage.client.fget_object(storage.bucket_name, f_rec.storage_path, local_path)
                        local_resource_paths.append(local_path)
                        secondary_paths.append(local_path)
                    op_cfg["secondary_input_paths"] = secondary_paths

                elif op_type == "video_overlay" and "overlay_video_file_id" in op_cfg:
                    fid = op_cfg["overlay_video_file_id"]
                    f_rec = ensure_file_local(db, fid, task.user_id, storage)
                    local_path = os.path.join(temp_dir, f"{fid}_overlay_{f_rec.original_filename}")
                    storage.client.fget_object(storage.bucket_name, f_rec.storage_path, local_path)
                    local_resource_paths.append(local_path)
                    op_cfg["overlay_file_path"] = local_path # Correct key for VideoProcessor 

                elif op_type == "audio_overlay" and "audio_file_id" in op_cfg:
                    fid = op_cfg["audio_file_id"]
                    f_rec = ensure_file_local(db, fid, task.user_id, storage)
                    local_path = os.path.join(temp_dir, f"{fid}_audio_{f_rec.original_filename}")
                    storage.client.fget_object(storage.bucket_name, f_rec.storage_path, local_path)
                    local_resource_paths.append(local_path)
                    op_cfg["audio_path"] = local_path

                elif op_type == "subtitles" and "subtitle_file_id" in op_cfg:
                    fid = op_cfg["subtitle_file_id"]
                    f_rec = ensure_file_local(db, fid, task.user_id, storage)
                    local_path = os.path.join(temp_dir, f"{fid}_subtitle_{f_rec.original_filename}")
                    storage.client.fget_object(storage.bucket_name, f_rec.storage_path, local_path)
                    local_resource_paths.append(local_path)
                    op_cfg["subtitle_file_path"] = local_path

            if len(operations) < 2:
                task.status = TaskStatus.FAILED
                task.error_message = "At least 2 operations required"
                db.commit()
                raise PermanentError("At least 2 operations required")
            if len(operations) > 10:
                task.status = TaskStatus.FAILED
                task.error_message = "Maximum 10 operations allowed"
                db.commit()
                raise PermanentError("Maximum 10 operations allowed")

            # Подготовка конфигурации для процессора
            processor_config = config.copy()
            processor_config["user_id"] = task.user_id
            processor_config["timeout"] = getattr(settings, "TASK_TIMEOUT", 3600)

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.combined_processor import CombinedProcessor

            processor = CombinedProcessor(
                task_id=task_id,
                config=processor_config,
                progress_callback=progress_cb
            )
            result = asyncio.run(processor.run())
        finally:
            # Cleanup
            for p in local_resource_paths:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            try:
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        result_file_id = result.get("result_file_id")
        if not result_file_id:
            raise PermanentError("Combined processing produced no result file")

        task.result = result
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        from datetime import datetime
        task.completed_at = datetime.utcnow()
        db.commit()
        return {"result_file_id": result_file_id, "status": "completed"}
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def subtitle_task(self, task_id: int, config: dict) -> dict:
    """
    Celery-задача наложения субтитров: скачать из MinIO -> SubtitleProcessor -> загрузить результат.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        # Получаем конфигурацию из запроса
        video_file_id = config.get("video_file_id")
        subtitle_file_id = config.get("subtitle_file_id")
        subtitle_text = config.get("subtitle_text")
        subtitle_format = config.get("format", "SRT")
        style = config.get("style")
        position = config.get("position")
        output_filename = config.get("output_filename", "subtitled.mp4")

        if not video_file_id:
            raise PermanentError("video_file_id is required")

        # Скачать видеофайл из MinIO
        from app.utils.temp_files import create_temp_dir, create_temp_file
        from app.storage.minio_client import MinIOClient
        import os

        storage = MinIOClient()
        temp_dir = create_temp_dir()
        local_paths = []

        try:
            # Ensure video file
            video_file = ensure_file_local(db, video_file_id, task.user_id, storage)
            
            video_path = os.path.join(temp_dir, f"{video_file.id}_{video_file.original_filename}")
            storage.client.fget_object(storage.bucket_name, video_file.storage_path, video_path)
            local_paths.append(video_path)

            # Скачать файл субтитров если есть
            subtitle_path = None
            if subtitle_file_id:
                subtitle_file = ensure_file_local(db, subtitle_file_id, task.user_id, storage)
                
                subtitle_path = os.path.join(temp_dir, f"{subtitle_file.id}_{subtitle_file.original_filename}")
                storage.client.fget_object(storage.bucket_name, subtitle_file.storage_path, subtitle_path)
                local_paths.append(subtitle_path)

            output_path = os.path.join(temp_dir, f"subtitle_{uuid.uuid4().hex}.mp4")

            # Конвертируем Pydantic модели в словари если нужно
            from app.schemas.subtitle import SubtitleFormat
            if isinstance(subtitle_format, str):
                subtitle_format = SubtitleFormat(subtitle_format)

            # Конвертируем style и position из словарей если нужно
            from app.schemas.subtitle import SubtitleStyle, SubtitlePosition
            if isinstance(style, dict):
                style = SubtitleStyle(**style)
            if isinstance(position, dict):
                position = SubtitlePosition(**position)

            subtitle_config = {
                "video_path": video_path,
                "subtitle_file_path": subtitle_path,
                "subtitle_text": subtitle_text,
                "format": subtitle_format,
                "style": style,
                "position": position,
                "output_path": output_path,
                "timeout": getattr(settings, "TASK_TIMEOUT", 3600),
            }

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.subtitle_processor import SubtitleProcessor

            processor = SubtitleProcessor(task_id=task_id, config=subtitle_config, progress_callback=progress_cb)
            result = asyncio.run(processor.run())

            out_path = result.get("output_path")
            if not out_path or not os.path.isfile(out_path):
                raise PermanentError("Subtitle processing produced no output file")

            # Загрузить результат в MinIO и создать запись File
            object_name = f"{task.user_id}/subtitle_{uuid.uuid4().hex}.mp4"
            storage.client.fput_object(
                storage.bucket_name,
                object_name,
                out_path,
                content_type="video/mp4",
            )
            size = os.path.getsize(out_path)
            new_file = File(
                user_id=task.user_id,
                filename=object_name,
                original_filename=output_filename,
                size=size,
                content_type="video/mp4",
                storage_path=object_name,
            )
            db.add(new_file)
            db.flush()

            output_files = list(task.output_files) if isinstance(task.output_files, list) else []
            output_files.append(new_file.id)
            task.output_files = output_files
            task.result = {"output_file_id": new_file.id, "object_name": object_name}
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            db.commit()
            return {"output_file_id": new_file.id, "status": "completed"}
        finally:
            for p in local_paths:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            try:
                if os.path.isdir(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def text_overlay_task(self, task_id: int, config: dict) -> dict:
    """
    Celery задача для наложения текста на видео.
    Скачать из MinIO -> TextOverlay -> загрузить результат.
    """
    settings = get_settings()
    db: Session = get_db_sync()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise PermanentError(f"Task {task_id} not found")
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}

        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        # Проверка video_file_id
        video_file_id = config.get("video_file_id")
        if not video_file_id:
            task.status = TaskStatus.FAILED
            task.error_message = "video_file_id is required"
            db.commit()
            raise PermanentError("video_file_id is required")

        # Скачать видео из MinIO во временную директорию
        from app.utils.temp_files import create_temp_dir, create_temp_file
        from app.storage.minio_client import MinIOClient
        import os

        storage = MinIOClient()
        temp_dir = create_temp_dir()

        try:
            # Ensure file is local (download if remote)
            file_record = ensure_file_local(db, video_file_id, task.user_id, storage)

            local_path = os.path.join(temp_dir, f"{video_file_id}_{file_record.original_filename}")
            storage.client.fget_object(storage.bucket_name, file_record.storage_path, local_path)

            # Формируем конфигурацию для процессора
            processor_config = config.copy()
            processor_config["video_path"] = local_path
            processor_config["output_path"] = os.path.join(
                temp_dir,
                f"text_overlay_{uuid.uuid4().hex}.mp4"
            )
            processor_config["timeout"] = getattr(settings, "TASK_TIMEOUT", 3600)

            progress_updates = {"progress": 0.0}

            def progress_cb(p: float) -> None:
                progress_updates["progress"] = p
                task.progress = p
                db.commit()

            from app.processors.text_overlay import TextOverlay

            processor = TextOverlay(
                task_id=task_id,
                config=processor_config,
                progress_callback=progress_cb
            )
            result = asyncio.run(processor.run())

            out_path = result.get("output_path")
            if not out_path or not os.path.isfile(out_path):
                raise PermanentError("Text overlay produced no output file")

            # Загрузить результат в MinIO и создать запись File
            output_filename = config.get("output_filename", "text_overlay.mp4")
            object_name = f"{task.user_id}/text_overlay_{uuid.uuid4().hex}.mp4"
            storage.client.fput_object(
                storage.bucket_name,
                object_name,
                out_path,
                content_type="video/mp4",
            )
            size = os.path.getsize(out_path)
            new_file = File(
                user_id=task.user_id,
                filename=object_name,
                original_filename=output_filename,
                size=size,
                content_type="video/mp4",
                storage_path=object_name,
            )
            db.add(new_file)
            db.flush()

            output_files = list(task.output_files) if isinstance(task.output_files, list) else []
            output_files.append(new_file.id)
            task.output_files = output_files
            task.result = {"output_file_id": new_file.id, "object_name": object_name}
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            db.commit()
            return {"output_file_id": new_file.id, "status": "completed"}
        finally:
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
            except OSError:
                pass
            try:
                out_path = processor_config.get("output_path")
                if out_path and os.path.exists(out_path):
                    os.remove(out_path)
            except OSError:
                pass
            try:
                if os.path.isdir(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    except PermanentError as e:
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    except Exception as e:
        if task is None:
            task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        db.close()
