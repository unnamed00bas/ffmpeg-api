"""
Tasks API: create, list, get, cancel, retry, join
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, get_db
from app.database.models.task import TaskStatus, TaskType
from app.database.models.user import User
from app.schemas.task import TaskListResponse, TaskResponse
from app.schemas.text_overlay import TextOverlayRequest
from app.schemas.audio_overlay import AudioOverlayRequest
from app.services.task_service import TaskService
from app.services.file_service import FileService
from app.queue.tasks import join_video_task, subtitle_task, text_overlay_task, video_overlay_task, audio_overlay_task
from app.schemas.video_overlay import VideoOverlayRequest
from app.schemas.combined import CombinedRequest
from app.schemas.common import FileSource
from app.database.models.file import File

router = APIRouter()


async def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


async def get_file_service(db: AsyncSession = Depends(get_db)) -> FileService:
    return FileService(db)


async def _resolve_file_id(
    source: FileSource,
    user_id: int,
    file_service: FileService,
) -> int:
    """Resolve FileSource to file ID (registering remote file if needed)."""
    if isinstance(source, int):
        return source
    if isinstance(source, (str, object)): # object needed for Pydantic v2 Url? or just str
        # Pydantic HttpUrl might be an object, but str(url) works
        file = await file_service.register_remote_file(user_id, str(source))
        return file.id
    raise HTTPException(status_code=422, detail="Invalid file source")


class TaskCreateBody(BaseModel):
    """Тело запроса создания задачи (универсальное)."""

    type: TaskType
    config: dict
    file_ids: Optional[List[FileSource]] = None
    priority: int = 5


class JoinTaskBody(BaseModel):
    """Тело запроса объединения видео."""

    file_ids: List[FileSource]
    output_filename: str = "joined.mp4"


class CombinedTaskBody(BaseModel):
    """Тело запроса комбинированных операций."""

    base_file_id: FileSource
    operations: List[dict]
    output_filename: Optional[str] = None


@router.post(
    "/join",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_join_task(
    body: JoinTaskBody,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу объединения видео.
    Требуется минимум 2 файла; файлы должны принадлежать пользователю.
    """
    file_ids: List[int] = []
    for fid_source in body.file_ids:
        fid = await _resolve_file_id(fid_source, current_user.id, file_service)
        file_ids.append(fid)

    if len(file_ids) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 files required for join",
        )
    for fid in file_ids:
        f = await file_service.get_file_info(fid, current_user.id)
        if not f:
            raise HTTPException(status_code=404, detail=f"File {fid} not found")
    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.JOIN,
        config={
            "output_filename": body.output_filename,
        },
        input_files=file_ids,
        output_files=[],
        priority=5,
    )
    join_video_task.delay(task.id, {"output_filename": body.output_filename})
    return service._task_to_response(task)


@router.post(
    "/combined",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_combined_task(
    body: CombinedTaskBody,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу комбинированных операций.
    Требуется base_file_id и список операций (2-10 операций).
    """
    # Валидация количества операций
    if len(body.operations) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 operations required for combined task",
        )
    if len(body.operations) > 10:
        raise HTTPException(
            status_code=422,
            detail="Maximum 10 operations allowed for combined task",
        )
    
    # Проверка base файла
    base_file_id = await _resolve_file_id(body.base_file_id, current_user.id, file_service)
    base_file = await file_service.get_file_info(base_file_id, current_user.id)
    if not base_file:
        raise HTTPException(
            status_code=404,
            detail=f"Base file {base_file_id} not found",
        )
    
    # Подготовка конфигурации
    operations_config = []
    for op in body.operations:
        op_dict = op.model_dump()
        op_type = op_dict.get("type")
        op_cfg = op_dict.get("config", {})

        # Resolve known file fields
        if op_type == "video_overlay" and "overlay_video_file_id" in op_cfg:
            op_cfg["overlay_video_file_id"] = await _resolve_file_id(
                op_cfg["overlay_video_file_id"], current_user.id, file_service
            )
        elif op_type == "audio_overlay" and "audio_file_id" in op_cfg:
            op_cfg["audio_file_id"] = await _resolve_file_id(
                op_cfg["audio_file_id"], current_user.id, file_service
            )
        elif op_type == "subtitles" and "subtitle_file_id" in op_cfg:
            op_cfg["subtitle_file_id"] = await _resolve_file_id(
                op_cfg["subtitle_file_id"], current_user.id, file_service
            )
        elif op_type == "join" and "file_ids" in op_cfg:
            resolved_ids = []
            for fid in op_cfg["file_ids"]:
                resolved_ids.append(await _resolve_file_id(fid, current_user.id, file_service))
            op_cfg["file_ids"] = resolved_ids
        
        op_dict["config"] = op_cfg
        operations_config.append(op_dict)

    config = {
        "operations": operations_config,
        "base_file_id": base_file_id,
        "output_filename": body.output_filename or f"combined_{base_file_id}.mp4",
    }
    
    # Создание задачи
    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.COMBINED,
        config=config,
        input_files=[base_file_id],
        output_files=[],
        priority=5,
    )
    
    # Запуск Celery задачи
    combined_task.delay(task.id, config)
    
    return service._task_to_response(task)


@router.post(
    "/video-overlay",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_video_overlay_task(
    body: VideoOverlayRequest,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу picture-in-picture (video overlay).
    Требуется base и overlay видео файлы.
    """

    # Check base file exists and belongs to user
    base_fid = await _resolve_file_id(body.base_video_file_id, current_user.id, file_service)
    base_file = await file_service.get_file_info(base_fid, current_user.id)
    if not base_file:
        raise HTTPException(status_code=404, detail=f"Base file {base_fid} not found")

    # Check overlay file exists and belongs to user
    overlay_fid = await _resolve_file_id(body.overlay_video_file_id, current_user.id, file_service)
    overlay_file = await file_service.get_file_info(overlay_fid, current_user.id)
    if not overlay_file:
        raise HTTPException(status_code=404, detail=f"Overlay file {overlay_fid} not found")

    # Update config with resolved IDs
    config_dict = body.to_dict()
    config_dict["base_video_file_id"] = base_fid
    config_dict["overlay_video_file_id"] = overlay_fid

    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.VIDEO_OVERLAY,
        config=config_dict,
        input_files=[base_fid, overlay_fid],
        output_files=[],
        priority=5,
    )

    video_overlay_task.delay(task.id, config_dict)
    return service._task_to_response(task)


@router.post(
    "/text-overlay",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_text_overlay_task(
    body: TextOverlayRequest,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу наложения текста на видео.
    """

    # Check video file exists and belongs to user
    video_fid = await _resolve_file_id(body.video_file_id, current_user.id, file_service)
    video_file = await file_service.get_file_info(video_fid, current_user.id)
    if not video_file:
        raise HTTPException(status_code=404, detail=f"Video file {video_fid} not found")

    config_dict = body.model_dump()
    config_dict["video_file_id"] = video_fid

    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.TEXT_OVERLAY,
        config=config_dict,
        input_files=[video_fid],
        output_files=[],
        priority=5,
    )
    text_overlay_task.delay(task.id, config_dict)
    return service._task_to_response(task)


@router.post(
    "/audio-overlay",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_audio_overlay_task(
    body: AudioOverlayRequest,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу наложения аудио на видео.
    Требуется видеофайл и аудиофайл.
    """

    # Check video file exists and belongs to user
    video_fid = await _resolve_file_id(body.video_file_id, current_user.id, file_service)
    video_file = await file_service.get_file_info(video_fid, current_user.id)
    if not video_file:
        raise HTTPException(status_code=404, detail=f"Video file {video_fid} not found")

    # Check audio file exists and belongs to user
    audio_fid = await _resolve_file_id(body.audio_file_id, current_user.id, file_service)
    audio_file = await file_service.get_file_info(audio_fid, current_user.id)
    if not audio_file:
        raise HTTPException(status_code=404, detail=f"Audio file {audio_fid} not found")

    config_dict = body.model_dump()
    config_dict["video_file_id"] = video_fid
    config_dict["audio_file_id"] = audio_fid

    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.AUDIO_OVERLAY,
        config=config_dict,
        input_files=[video_fid, audio_fid],
        output_files=[],
        priority=5,
    )
    audio_overlay_task.delay(task.id, config_dict)
    return service._task_to_response(task)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateBody,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """Создать задачу обработки (общий endpoint)."""
    
    # Resolve inputs
    input_files_ids = []
    if body.file_ids:
        for fid_source in body.file_ids:
            resolved_id = await _resolve_file_id(fid_source, current_user.id, file_service)
            input_files_ids.append(resolved_id)

    task = await service.create_task(
        user_id=current_user.id,
        task_type=body.type,
        config=body.config,
        input_files=input_files_ids,
        output_files=[],
        priority=body.priority,
    )
    if body.type == TaskType.JOIN and input_files_ids and len(input_files_ids) >= 2:
        join_video_task.delay(
            task.id,
            body.config if isinstance(body.config, dict) else {"output_filename": "joined.mp4"},
        )
    return service._task_to_response(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    type_filter: Optional[TaskType] = Query(None, alias="type"),
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
):
    """Список задач пользователя с фильтрами и пагинацией."""
    return await service.get_tasks(
        user_id=current_user.id,
        status=status_filter,
        task_type=type_filter,
        offset=offset,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
):
    """Получить задачу по ID."""
    task = await service.get_task(task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return service._task_to_response(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
):
    """Отменить задачу (PENDING или PROCESSING)."""
    ok = await service.cancel_task(task_id, current_user.id)
    if not ok:
        task = await service.get_task(task_id, current_user.id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(
            status_code=400,
            detail="Task cannot be cancelled (already completed or failed)",
        )
    task = await service.get_task(task_id, current_user.id)
    return service._task_to_response(task)


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
):
    """Повторить неудавшуюся задачу."""
    task = await service.retry_task(task_id, current_user.id)
    if not task:
        t = await service.get_task(task_id, current_user.id)
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(
            status_code=400,
            detail="Only failed tasks can be retried",
        )
    if task.type == TaskType.JOIN and task.input_files and len(task.input_files) >= 2:
        config = task.config or {}
        join_video_task.delay(
            task.id,
            config if isinstance(config, dict) else {"output_filename": "joined.mp4"},
        )
    elif task.type == TaskType.AUDIO_OVERLAY and task.input_files and len(task.input_files) == 2:
        config = task.config or {}
        audio_overlay_task.delay(
            task.id,
            config if isinstance(config, dict) else {},
        )
    return service._task_to_response(task)


class SubtitleTaskBody(BaseModel):
    """Тело запроса наложения субтитров."""

    video_file_id: FileSource
    subtitle_file_id: Optional[FileSource] = None
    subtitle_text: Optional[List[Dict[str, Any]]] = None
    format: str = "SRT"
    style: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None
    output_filename: str = "subtitled.mp4"


@router.post(
    "/subtitles",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtitle_task(
    body: SubtitleTaskBody,
    current_user: User = Depends(get_current_active_user),
    service: TaskService = Depends(get_task_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    Создать задачу наложения субтитров на видео.
    Можно указать subtitle_file_id или subtitle_text (но не оба).
    """
    # Проверяем видеофайл
    video_fid = await _resolve_file_id(body.video_file_id, current_user.id, file_service)
    video_file = await file_service.get_file_info(video_fid, current_user.id)
    if not video_file:
        raise HTTPException(status_code=404, detail=f"Video file {video_fid} not found")

    # Проверяем файл субтитров если указан
    subtitle_fid = None
    if body.subtitle_file_id:
        subtitle_fid = await _resolve_file_id(body.subtitle_file_id, current_user.id, file_service)
        subtitle_file = await file_service.get_file_info(subtitle_fid, current_user.id)
        if not subtitle_file:
            raise HTTPException(status_code=404, detail=f"Subtitle file {subtitle_fid} not found")

    # Проверяем, что указан хотя бы один источник субтитров
    if not subtitle_fid and not body.subtitle_text:
        raise HTTPException(
            status_code=422,
            detail="Either subtitle_file_id or subtitle_text must be provided"
        )

    # Подготовка конфигурации
    config = {
        "video_file_id": video_fid,
        "subtitle_file_id": subtitle_fid,
        "subtitle_text": body.subtitle_text,
        "format": body.format,
        "style": body.style,
        "position": body.position,
        "output_filename": body.output_filename,
    }

    # Создаем задачу
    task = await service.create_task(
        user_id=current_user.id,
        task_type=TaskType.SUBTITLES,
        config=config,
        input_files=[video_fid] + ([subtitle_fid] if subtitle_fid else []),
        output_files=[],
        priority=5,
    )

    # Запускаем Celery задачу
    subtitle_task.delay(task.id, config)
    return service._task_to_response(task)