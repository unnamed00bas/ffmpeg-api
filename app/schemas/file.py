"""
File Pydantic schemas for API request/response
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UploadFromUrlRequest(BaseModel):
    """Тело запроса загрузки по URL."""

    url: str


class FileMetadata(BaseModel):
    """Метаданные медиа-файла (из ffprobe или загрузки)."""

    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[int] = None


class FileUploadResponse(BaseModel):
    """Ответ после загрузки файла."""

    id: int
    filename: str
    original_filename: str
    size: int
    content_type: str
    metadata: Optional[FileMetadata] = None
    created_at: datetime
    download_url: str


class FileInfo(BaseModel):
    """Информация о файле (без download_url)."""

    id: int
    original_filename: str
    size: int
    content_type: str
    metadata: Optional[FileMetadata] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Список файлов с пагинацией."""

    files: List[FileInfo]
    total: int
    page: int
    page_size: int
