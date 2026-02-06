"""
Caching middleware for Strands API.

Implements:
- In-memory caching for frequent read operations
- Cache invalidation strategies
- Response compression (Gzip)
"""

import time
import logging
import hashlib
import json
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

class CacheMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory cache middleware.
    
    In production, use Redis or Memcached for distributed caching.
    """
    
    def __init__(
        self, 
        app: ASGIApp, 
        ttl: int = 60, 
        max_size: int = 1000,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.ttl = ttl
        self.max_size = max_size
        self.cache = {}
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics"]
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)
            
        # Check excluded paths
        for path in self.exclude_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
                
        # Generate cache key
        cache_key = self._generate_key(request)
        
        # Check cache
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            logger.debug(f"Cache hit for {request.url.path}")
            return Response(
                content=cached_response["content"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response["media_type"]
            )
            
        # Process request
        response = await call_next(request)
        
        # Cache successful responses
        if response.status_code == 200:
            # We need to read the response body to cache it
            # This is tricky with streaming responses, so we handle standard responses
            # Handle Starlette/FastAPI Response object
            if hasattr(response, "body"):
                content = response.body
            else:
                # Fallback for streaming responses (simplified for this example)
                content = b""
                async for chunk in response.body_iterator:
                    content += chunk
                # Reset iterator for downstream
                async def iterator():
                    yield content
                response.body_iterator = iterator()
            
            self._add_to_cache(cache_key, {
                "content": content,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "timestamp": time.time()
            })
            
        return response
        
    def _generate_key(self, request: Request) -> str:
        """Generate a unique cache key based on URL and query params."""
        key_str = f"{request.method}:{request.url.path}:{str(sorted(request.query_params.items()))}"
        return hashlib.md5(key_str.encode()).hexdigest()
        
    def _get_from_cache(self, key: str) -> Optional[dict]:
        """Retrieve item from cache if valid."""
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item["timestamp"] < self.ttl:
                return item
            else:
                del self.cache[key]  # Expired
        return None
        
    def _add_to_cache(self, key: str, value: dict):
        """Add item to cache with eviction policy."""
        if len(self.cache) >= self.max_size:
            # Simple LRU-like: remove oldest item (based on timestamp)
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]
            
        self.cache[key] = value

# Example usage in FastAPI app:
"""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from cache_middleware import CacheMiddleware

app = FastAPI()

# Add Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add caching
app.add_middleware(CacheMiddleware, ttl=60)
"""
