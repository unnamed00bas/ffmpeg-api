"""
Files API: upload, download, list, delete, chunked upload, range download
"""
import re
from io import BytesIO

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, get_db
from app.database.models.user import User
from app.schemas.file import FileInfo, FileListResponse, FileUploadResponse, UploadFromUrlRequest
from app.services.file_service import FileService
from app.services.chunk_upload import ChunkUploadManager

router = APIRouter()


async def get_file_service(db: AsyncSession = Depends(get_db)) -> FileService:
    return FileService(db)


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Загрузка файла (multipart/form-data)."""
    content = await file.read()
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename required")
    try:
        f = await service.upload_from_request(
            user_id=current_user.id,
            filename=file.filename,
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    download_url = await service.get_download_url(f)
    return FileUploadResponse(
        id=f.id,
        filename=f.filename,
        original_filename=f.original_filename,
        size=f.size,
        content_type=f.content_type,
        metadata=service._file_to_metadata(f.file_metadata),
        created_at=f.created_at,
        download_url=download_url,
    )


@router.post(
    "/upload-url",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_from_url(
    body: UploadFromUrlRequest,
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Загрузка файла по URL."""
    url = body.url
    try:
        f = await service.upload_from_url(current_user.id, url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Download failed: {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Download timeout")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    download_url = await service.get_download_url(f)
    return FileUploadResponse(
        id=f.id,
        filename=f.filename,
        original_filename=f.original_filename,
        size=f.size,
        content_type=f.content_type,
        metadata=service._file_to_metadata(f.file_metadata),
        created_at=f.created_at,
        download_url=download_url,
    )


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Информация о файле."""
    f = await service.get_file_info(file_id, current_user.id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return FileInfo(
        id=f.id,
        original_filename=f.original_filename,
        size=f.size,
        content_type=f.content_type,
        metadata=service._file_to_metadata(f.file_metadata),
        created_at=f.created_at,
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Скачивание файла (stream)."""
    data = await service.download_file(file_id, current_user.id)
    if data is None:
        raise HTTPException(status_code=404, detail="File not found")
    f = await service.get_file_info(file_id, current_user.id)
    return StreamingResponse(
        BytesIO(data),
        media_type=f.content_type if f else "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{f.original_filename}"' if f else "attachment",
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Удаление файла."""
    ok = await service.delete_file(file_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("", response_model=FileListResponse)
async def list_files(
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Список файлов пользователя с пагинацией."""
    files = await service.get_user_files(current_user.id, offset=offset, limit=limit)
    total = await service.get_user_files_count(current_user.id)
    return FileListResponse(
        files=[
            FileInfo(
                id=f.id,
                original_filename=f.original_filename,
                size=f.size,
                content_type=f.content_type,
                metadata=service._file_to_metadata(f.file_metadata),
                created_at=f.created_at,
            )
            for f in files
        ],
        total=total,
        page=offset // limit + 1 if limit else 1,
        page_size=limit,
    )


# ----- Chunked upload (streaming для больших файлов) -----

@router.post("/upload-init")
async def initiate_chunk_upload(
    filename: str = Form(...),
    total_size: int = Form(...),
    total_chunks: int = Form(...),
    content_type: str = Form(...),
    current_user: User = Depends(get_current_active_user),
):
    """Инициализация загрузки по чанкам; возвращает upload_id."""
    manager = ChunkUploadManager()
    upload_id = await manager.initiate_upload(
        current_user.id,
        filename,
        total_size,
        total_chunks,
        content_type,
    )
    return {"upload_id": upload_id}


@router.post("/upload-chunk/{upload_id}/{chunk_number}")
async def upload_chunk(
    upload_id: str,
    chunk_number: int,
    chunk_data: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Загрузка одного чанка."""
    manager = ChunkUploadManager()
    info = await manager.get_upload_info(upload_id)
    if not info or info.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    chunk_bytes = await chunk_data.read()
    success = await manager.upload_chunk(upload_id, chunk_number, chunk_bytes)
    if not success:
        raise HTTPException(status_code=400, detail="Chunk upload failed")
    return {"status": "uploaded", "chunk_number": chunk_number}


@router.post("/upload-complete/{upload_id}", response_model=FileUploadResponse)
async def complete_upload(
    upload_id: str,
    output_filename: str | None = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    """Завершение загрузки: сборка чанков и создание файла."""
    manager = ChunkUploadManager()
    try:
        file_record = await manager.complete_upload(upload_id, db, output_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not file_record:
        raise HTTPException(status_code=404, detail="Upload not found")
    if file_record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    download_url = await service.get_download_url(file_record)
    return FileUploadResponse(
        id=file_record.id,
        filename=file_record.filename,
        original_filename=file_record.original_filename,
        size=file_record.size,
        content_type=file_record.content_type,
        metadata=service._file_to_metadata(file_record.file_metadata),
        created_at=file_record.created_at,
        download_url=download_url,
    )


@router.post("/upload-abort/{upload_id}")
async def abort_upload(
    upload_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Отмена загрузки по чанкам."""
    manager = ChunkUploadManager()
    info = await manager.get_upload_info(upload_id)
    if not info or info.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    await manager.abort_upload(upload_id)
    return {"status": "aborted"}


# ----- Range download (streaming скачивание) -----

@router.get("/{file_id}/download-range")
async def download_file_range(
    file_id: int,
    range_header: str | None = Header(None, alias="Range"),
    current_user: User = Depends(get_current_active_user),
    service: FileService = Depends(get_file_service),
):
    """Скачивание с поддержкой Range (для больших файлов и докачки)."""
    f = await service.get_file_info(file_id, current_user.id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    file_size = f.size
    start, end = 0, file_size - 1
    if range_header:
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
            else:
                end = file_size - 1
    content_length = end - start + 1

    def generate():
        from app.storage.minio_client import MinIOClient
        storage = MinIOClient()
        response = storage.get_object_stream(f.storage_path)
        try:
            to_skip = start
            chunk_size = 8192
            while to_skip > 0:
                data = response.read(min(chunk_size, to_skip))
                if not data:
                    break
                to_skip -= len(data)
            remaining = content_length
            while remaining > 0:
                data = response.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
        finally:
            response.close()
            response.release_conn()

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": f.content_type or "application/octet-stream",
        "Content-Disposition": f'attachment; filename="{f.original_filename}"',
    }
    return StreamingResponse(
        generate(),
        status_code=206 if range_header else 200,
        headers=headers,
    )