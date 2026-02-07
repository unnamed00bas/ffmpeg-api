"""
Health check endpoints
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    """Проверка здоровья приложения"""
    return {
        "success": True,
        "status": "healthy",
        "message": "FFmpeg API Service is running"
    }
