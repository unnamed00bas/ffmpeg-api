"""
Rate limiting middleware
"""
from fastapi import Request, HTTPException
from collections import defaultdict
import time
from app.config import settings

# Простая реализация in-memory rate limiting
# В production рекомендуется использовать Redis-based решение


class RateLimitMiddleware:
    """Middleware для ограничения частоты запросов (ASGI-совместимый)"""

    def __init__(self, app):
        self.app = app
        self.requests = defaultdict(list)

    async def __call__(self, scope, receive, send):
        """Обработка запроса с rate limiting"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Создаём Request из scope
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        
        request = Request(scope, receive, send)
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Удаление старых запросов (старше 1 минуты)
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]

        # Проверка лимитов
        minute_requests = len(self.requests[client_ip])
        if minute_requests >= settings.RATE_LIMIT_PER_MINUTE:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
            await response(scope, receive, send)
            return

        # Добавление текущего запроса
        self.requests[client_ip].append(current_time)

        # Выполнение запроса через app
        await self.app(scope, receive, send)
