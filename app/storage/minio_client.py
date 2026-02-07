"""
MinIO client for file storage (sync API wrapped in asyncio)
"""
import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

from minio import Minio

from app.config import get_settings

settings = get_settings()


class MinIOClient:
    """Клиент MinIO: загрузка, скачивание, удаление, presigned URL."""

    def __init__(self):
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    async def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: str,
    ) -> str:
        """
        Загрузка файла в MinIO.

        Args:
            file_path: Локальный путь к файлу
            object_name: Имя объекта в бакете
            content_type: MIME-тип

        Returns:
            object_name (путь в бакете)
        """
        await asyncio.to_thread(
            self.client.fput_object,
            self.bucket_name,
            object_name,
            file_path,
            content_type=content_type,
        )
        return object_name

    async def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str,
    ) -> str:
        """Загрузка из байтов (для небольших файлов)."""
        from io import BytesIO
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket_name,
            object_name,
            BytesIO(data),
            len(data),
            content_type=content_type,
        )
        return object_name

    async def download_file(
        self,
        object_name: str,
        file_path: str,
    ) -> None:
        """Скачивание объекта в локальный файл."""
        await asyncio.to_thread(
            self.client.fget_object,
            self.bucket_name,
            object_name,
            file_path,
        )

    async def get_file_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Генерация presigned GET URL."""
        url = await asyncio.to_thread(
            self.client.presigned_get_object,
            self.bucket_name,
            object_name,
            expires=expires,
        )
        return url

    async def delete_file(self, object_name: str) -> None:
        """Удаление объекта."""
        await asyncio.to_thread(
            self.client.remove_object,
            self.bucket_name,
            object_name,
        )

    async def file_exists(self, object_name: str) -> bool:
        """Проверка существования объекта (stat)."""
        try:
            await asyncio.to_thread(
                self.client.stat_object,
                self.bucket_name,
                object_name,
            )
            return True
        except Exception:
            return False

    async def get_file_info(self, object_name: str) -> Dict[str, Any]:
        """Метаданные объекта (size, etag, last_modified)."""
        stat = await asyncio.to_thread(
            self.client.stat_object,
            self.bucket_name,
            object_name,
        )
        return {
            "size": stat.size,
            "etag": stat.etag,
            "last_modified": stat.last_modified,
        }

    def list_objects(self, prefix: str = "") -> list:
        """Список имён объектов с заданным префиксом (sync)."""
        objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    async def list_objects_async(self, prefix: str = "") -> list:
        """Список имён объектов с заданным префиксом."""
        return await asyncio.to_thread(self.list_objects, prefix)

    async def get_object_bytes(self, object_name: str) -> bytes:
        """Чтение объекта в байты."""
        response = await asyncio.to_thread(
            self.client.get_object,
            self.bucket_name,
            object_name,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_object_stream(self, object_name: str):
        """Синхронный поток чтения объекта (для range download)."""
        return self.client.get_object(self.bucket_name, object_name)
