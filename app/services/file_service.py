"""
File upload, validation and storage service
"""
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models.file import File
from app.database.repositories.file_repository import FileRepository
from app.schemas.file import FileMetadata, FileUploadResponse, FileInfo
from app.storage.minio_client import MinIOClient

settings = get_settings()

# Разрешённые MIME-типы по категориям (для валидации)
ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/avi",
    "video/quicktime",
    "video/x-matroska",
    "video/x-ms-wmv",
    "audio/mpeg",
    "audio/aac",
    "audio/wav",
    "audio/flac",
    "audio/ogg",
    "text/plain",
    "text/vtt",
    "text/x-ssa",
}


class FileService:
    """Сервис работы с файлами: загрузка, валидация, MinIO, БД."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._repo = FileRepository(session)
        self._storage = MinIOClient()

    def _allowed_extensions(self) -> set:
        return (
            set(settings.ALLOWED_VIDEO_EXTENSIONS)
            | set(settings.ALLOWED_AUDIO_EXTENSIONS)
            | set(settings.ALLOWED_SUBTITLE_EXTENSIONS)
        )

    async def validate_file(
        self,
        filename: str,
        content_type: str,
        size: int,
    ) -> bool:
        """Проверка: расширение, content-type, размер."""
        if size <= 0 or size > settings.MAX_UPLOAD_SIZE:
            return False
        ext = (filename.rsplit(".", 1)[-1].lower() if "." in filename else "") or ""
        if ext not in self._allowed_extensions():
            return False
        if content_type not in ALLOWED_CONTENT_TYPES:
            return False
        return True

    def _storage_path(self, user_id: int, filename: str) -> str:
        """Путь в MinIO: user_id/uuid_safe_filename."""
        safe = f"{uuid.uuid4().hex}_{filename}"
        return f"{user_id}/{safe}"

    @staticmethod
    def _file_to_metadata(meta: Optional[Dict[str, Any]]) -> Optional[FileMetadata]:
        if not meta:
            return None
        return FileMetadata(
            duration=meta.get("duration"),
            width=meta.get("width"),
            height=meta.get("height"),
            video_codec=meta.get("video_codec"),
            audio_codec=meta.get("audio_codec"),
            bitrate=meta.get("bitrate"),
        )

    async def upload_from_request(
        self,
        user_id: int,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> File:
        """Загрузка файла из запроса: валидация -> MinIO -> запись в БД."""
        if not await self.validate_file(filename, content_type, len(content)):
            raise ValueError("File validation failed")
        storage_path = self._storage_path(user_id, filename)
        await self._storage.upload_bytes(content, storage_path, content_type)
        file = await self._repo.create(
            user_id=user_id,
            filename=storage_path,
            original_filename=filename,
            size=len(content),
            content_type=content_type,
            storage_path=storage_path,
            metadata=metadata,
        )
        await self._session.commit()
        await self._session.refresh(file)
        return file

    async def upload_from_url(
        self,
        user_id: int,
        url: str,
        timeout: int = 60,
    ) -> File:
        """Скачивание файла по URL и загрузка в хранилище."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            # Имя из URL или Content-Disposition
            filename = url.rstrip("/").split("/")[-1].split("?")[0] or "download"
            content_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        return await self.upload_from_request(user_id, filename, content, content_type)

    async def register_remote_file(
        self,
        user_id: int,
        url: str,
    ) -> File:
        """Регистрация удаленного файла без скачивания (lazy download)."""
        filename = url.rstrip("/").split("/")[-1].split("?")[0] or "remote_file"
        # storage_path holds the URL temporarily
        file = await self._repo.create(
            user_id=user_id,
            filename=filename,
            original_filename=filename,
            size=0,
            content_type="application/octet-stream",
            storage_path=url,
            metadata={"is_remote": True},
        )
        await self._session.commit()
        await self._session.refresh(file)
        return file

    async def get_file_info(self, file_id: int, user_id: int) -> Optional[File]:
        """Файл по ID с проверкой владельца (и не удалён)."""
        file = await self._repo.get_by_id(file_id)
        if not file or file.user_id != user_id or file.is_deleted:
            return None
        return file

    async def get_user_files(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> List[File]:
        """Список файлов пользователя (без удалённых)."""
        return await self._repo.get_by_user(user_id=user_id, offset=offset, limit=limit)

    async def get_user_files_count(self, user_id: int) -> int:
        """Общее количество файлов пользователя."""
        return await self._repo.get_user_file_count(user_id)

    async def delete_file(self, file_id: int, user_id: int) -> bool:
        """Удаление из MinIO и soft-delete в БД."""
        file = await self.get_file_info(file_id, user_id)
        if not file:
            return False
        try:
            await self._storage.delete_file(file.storage_path)
        except Exception:
            pass
        await self._repo.mark_as_deleted(file_id)
        await self._session.commit()
        return True

    async def download_file(
        self,
        file_id: int,
        user_id: int,
    ) -> Optional[bytes]:
        """Скачивание содержимого файла (через временный файл или get_object)."""
        file = await self.get_file_info(file_id, user_id)
        if not file:
            return None
        # Minio get_object returns a stream; read to bytes
        import asyncio
        from io import BytesIO
        def _get():
            r = self._storage.client.get_object(
                self._storage.bucket_name,
                file.storage_path,
            )
            return r.read()
        data = await asyncio.to_thread(_get)
        return data

    async def get_download_url(self, file: File, expires: timedelta = timedelta(hours=1)) -> str:
        """Presigned URL для скачивания."""
        return await self._storage.get_file_url(file.storage_path, expires=expires)