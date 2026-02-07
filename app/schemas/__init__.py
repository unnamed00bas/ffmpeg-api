"""
Pydantic schemas for API and services
"""
from app.schemas.task import (
    TaskType,
    TaskStatus,
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
)
from app.schemas.file import (
    FileMetadata,
    FileUploadResponse,
    FileInfo,
    FileListResponse,
)
try:
    from app.schemas.combined import (
        OperationType,
        Operation,
        CombinedRequest,
    )
except ImportError:
    # Схемы могут еще не быть имплементированы
    OperationType = None
    Operation = None
    CombinedRequest = None

try:
    from app.schemas.text_overlay import (
        TextPositionType,
        TextPosition,
        TextStyle,
        TextBackground,
        TextBorder,
        TextShadow,
        TextAnimationType,
        TextAnimation,
        TextOverlayRequest,
    )
except ImportError:
    # Схемы могут еще не быть имплементированы
    TextPositionType = None
    TextPosition = None
    TextStyle = None
    TextBackground = None
    TextBorder = None
    TextShadow = None
    TextAnimationType = None
    TextAnimation = None
    TextOverlayRequest = None

try:
    from app.schemas.subtitle import (
        SubtitleFormat,
        SubtitleStyle,
        SubtitlePosition,
        SubtitleRequest,
    )
except ImportError:
    # Схемы могут еще не быть имплементированы
    SubtitleFormat = None
    SubtitleStyle = None
    SubtitlePosition = None
    SubtitleRequest = None

try:
    from app.schemas.audio_overlay import (
        AudioOverlayMode,
        AudioOverlayRequest,
    )
except ImportError:
    AudioOverlayMode = None
    AudioOverlayRequest = None

try:
    from app.schemas.video_overlay import (
        OverlayShapeType,
        OverlayConfig,
        BorderStyle,
        ShadowStyle,
        VideoOverlayRequest,
    )
except ImportError:
    # Схемы могут еще не быть имплементированы
    OverlayShapeType = None
    OverlayConfig = None
    BorderStyle = None
    ShadowStyle = None
    VideoOverlayRequest = None

__all__ = [
    "TaskType",
    "TaskStatus",
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskListResponse",
    "FileMetadata",
    "FileUploadResponse",
    "FileInfo",
    "FileListResponse",
]

# Добавляем комбинированные схемы если они доступны
if OperationType is not None:
    __all__.extend([
        "OperationType",
        "Operation",
        "CombinedRequest",
    ])

# Добавляем схемы text overlay если они доступны
if TextPositionType is not None:
    __all__.extend([
        "TextPositionType",
        "TextPosition",
        "TextStyle",
        "TextBackground",
        "TextBorder",
        "TextShadow",
        "TextAnimationType",
        "TextAnimation",
        "TextOverlayRequest",
    ])

# Добавляем схемы subtitle если они доступны
if SubtitleFormat is not None:
    __all__.extend([
        "SubtitleFormat",
        "SubtitleStyle",
        "SubtitlePosition",
        "SubtitleRequest",
    ])

# Добавляем схемы video overlay если они доступны
if OverlayShapeType is not None:
    __all__.extend([
        "OverlayShapeType",
        "OverlayConfig",
        "BorderStyle",
        "ShadowStyle",
        "VideoOverlayRequest",
    ])

# Добавляем схемы audio overlay если они доступны
if AudioOverlayMode is not None:
    __all__.extend([
        "AudioOverlayMode",
        "AudioOverlayRequest",
    ])
