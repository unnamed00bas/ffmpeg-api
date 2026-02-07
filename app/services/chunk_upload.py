"""
Chunked upload: инициализация, загрузка чанков, сборка файла.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from redis import Redis

from app.config import get_settings
from app.database.models.file import File
from app.storage.minio_client import MinIOClient
from app.utils.temp_files import create_temp_file

_settings = get_settings()


class ChunkUploadManager:
    """Управление загрузкой файла по чанкам (состояние в Redis, чанки в MinIO)."""

    REDIS_PREFIX = "chunk_upload:"
    CHUNK_PREFIX = "temp/chunks/"
    CHUNK_TTL = 3600  # 1 hour

    def __init__(self) -> None:
        self._redis = Redis.from_url(_settings.REDIS_URL)
        self._storage = MinIOClient()

    def _run_sync(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return asyncio.get_event_loop().run_in_executor(
            None, lambda: fn(*args, **kwargs)
        )

    async def get_upload_info(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о сессии загрузки (для проверки владельца)."""
        key = f"{self.REDIS_PREFIX}{upload_id}"
        data = await self._run_sync(self._redis.get, key)
        if data:
            return json.loads(data)
        return None

    async def _set_upload_info(self, upload_id: str, info: Dict[str, Any]) -> None:
        key = f"{self.REDIS_PREFIX}{upload_id}"
        await self._run_sync(
            self._redis.setex,
            key,
            self.CHUNK_TTL,
            json.dumps(info),
        )

    async def initiate_upload(
        self,
        user_id: int,
        filename: str,
        total_size: int,
        total_chunks: int,
        content_type: str,
    ) -> str:
        """Создание сессии загрузки, возврат upload_id."""
        upload_id = str(uuid.uuid4())
        info = {
            "user_id": user_id,
            "filename": filename,
            "total_size": total_size,
            "total_chunks": total_chunks,
            "content_type": content_type,
            "uploaded_chunks": [],
            "created_at": datetime.utcnow().isoformat(),
        }
        await self._set_upload_info(upload_id, info)
        return upload_id

    async def upload_chunk(
        self,
        upload_id: str,
        chunk_number: int,
        chunk_data: bytes,
    ) -> bool:
        """Сохранение одного чанка в MinIO и обновление состояния."""
        info = await self.get_upload_info(upload_id)
        if not info:
            return False
        object_name = f"{self.CHUNK_PREFIX}{upload_id}_{chunk_number}"
        await self._storage.upload_bytes(
            chunk_data,
            object_name,
            "application/octet-stream",
        )
        if chunk_number not in info["uploaded_chunks"]:
            info["uploaded_chunks"].append(chunk_number)
            info["uploaded_chunks"].sort()
        await self._set_upload_info(upload_id, info)
        return True

    async def complete_upload(
        self,
        upload_id: str,
        db_session: Any,
        output_filename: Optional[str] = None,
    ) -> Optional[File]:
        """
        Сборка файла из чанков, загрузка в MinIO, создание записи File.
        db_session: AsyncSession для создания записи в БД.
        """
        from app.database.repositories.file_repository import FileRepository

        info = await self.get_upload_info(upload_id)
        if not info:
            return None
        total = info["total_chunks"]
        if len(info["uploaded_chunks"]) != total:
            raise ValueError("Not all chunks uploaded")
        user_id = info["user_id"]
        filename = output_filename or info["filename"]
        content_type = info["content_type"]
        total_size = info["total_size"]

        temp_path = create_temp_file(prefix="chunk_merge_")
        try:
            with open(temp_path, "wb") as out:
                for i in range(total):
                    object_name = f"{self.CHUNK_PREFIX}{upload_id}_{i}"
                    chunk_bytes = await self._storage.get_object_bytes(object_name)
                    out.write(chunk_bytes)
                    await self._storage.delete_file(object_name)

            storage_path = f"{user_id}/{uuid.uuid4().hex}_{filename}"
            await self._storage.upload_file(temp_path, storage_path, content_type)

            repo = FileRepository(db_session)
            file_record = await repo.create(
                user_id=user_id,
                filename=storage_path,
                original_filename=filename,
                size=total_size,
                content_type=content_type,
                storage_path=storage_path,
                metadata={},
            )
            await db_session.commit()
            await db_session.refresh(file_record)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        key = f"{self.REDIS_PREFIX}{upload_id}"
        await self._run_sync(self._redis.delete, key)
        return file_record

    async def abort_upload(self, upload_id: str) -> bool:
        """Удаление всех чанков и записи о загрузке."""
        info = await self.get_upload_info(upload_id)
        if not info:
            return False
        for chunk_num in info.get("uploaded_chunks", []):
            object_name = f"{self.CHUNK_PREFIX}{upload_id}_{chunk_num}"
            try:
                await self._storage.delete_file(object_name)
            except Exception:
                pass
        key = f"{self.REDIS_PREFIX}{upload_id}"
        await self._run_sync(self._redis.delete, key)
        return True
