"""
Security middleware for FastAPI application.

Implements:
- Input validation and sanitization
- Rate limiting
- CORS configuration
- Security headers
- Request/response logging
"""

import time
import logging
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import re

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.
    
    In production, use Redis-based rate limiting for distributed systems.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_history = {}

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self.request_history:
            self.request_history[client_ip] = [
                req_time for req_time in self.request_history[client_ip]
                if current_time - req_time < 60
            ]
        else:
            self.request_history[client_ip] = []

        # Check rate limit
        if len(self.request_history[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"}
            )

        self.request_history[client_ip].append(current_time)
        response = await call_next(request)
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Validates and sanitizes input data.
    
    Prevents:
    - SQL injection patterns
    - XSS attempts
    - Path traversal
    """

    DANGEROUS_PATTERNS = [
        r"(?i)(union|select|insert|update|delete|drop|create|alter)",  # SQL
        r"(?i)(<script|javascript:|onerror=|onclick=)",  # XSS
        r"(\.\./|\.\.\\)",  # Path traversal
        r"(%00|%0d|%0a)",  # Null bytes
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        # Validate query parameters
        for key, value in request.query_params.items():
            if self._is_dangerous(key) or self._is_dangerous(value):
                logger.warning(f"Dangerous input detected: {key}={value}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid input"}
                )

        response = await call_next(request)
        return response

    @staticmethod
    def _is_dangerous(value: str) -> bool:
        """Check if value contains dangerous patterns."""
        for pattern in InputValidationMiddleware.DANGEROUS_PATTERNS:
            if re.search(pattern, str(value)):
                return True
        return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all requests and responses for audit trail.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host}"
        )

        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"in {process_time:.3f}s"
        )

        response.headers["X-Process-Time"] = str(process_time)
        return response


def setup_security(app):
    """
    Configure all security middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Configure for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.example.com"]  # Configure for production
    )

    # Custom security middleware (order matters - add in reverse)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)


# Example usage in FastAPI app:
"""
from fastapi import FastAPI
from security_middleware import setup_security

app = FastAPI()
setup_security(app)

@app.get("/health")
async def health():
    return {"status": "healthy"}
"""
