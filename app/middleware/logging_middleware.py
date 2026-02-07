"""
Logging middleware
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех запросов"""

    async def dispatch(self, request: Request, call_next):
        """Обработка запроса"""
        start_time = time.time()

        # Логирование входящего запроса
        logger.info(f"Incoming request: {request.method} {request.url.path}")

        # Выполнение запроса
        response = await call_next(request)

        # Вычисление времени обработки
        process_time = (time.time() - start_time) * 1000

        # Добавление заголовка со временем обработки
        response.headers["X-Process-Time"] = str(process_time)

        # Логирование ответа
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Time: {process_time:.2f}ms"
        )

        return response
