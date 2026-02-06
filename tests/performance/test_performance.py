"""
Performance tests for Strands optimizations.
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch
from src.cache_middleware import CacheMiddleware
from src.async_task_manager import AsyncTaskManager
from fastapi import FastAPI, Request, Response

# Mock FastAPI app for middleware testing
app = FastAPI()

@app.get("/test-cache")
async def test_endpoint():
    # Simulate slow operation
    await asyncio.sleep(0.1)
    return {"data": "result"}

@pytest.mark.asyncio
async def test_cache_middleware_performance():
    """Test that caching improves response time."""
    middleware = CacheMiddleware(app, ttl=60)
    
    # Mock request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test-cache",
        "query_string": b"",
        "headers": [],
    }
    
    async def call_next(request):
        await asyncio.sleep(0.1)  # Simulate processing
        return Response(content=b'{"data": "result"}', media_type="application/json")
    
    # First call (cache miss)
    start_time = time.time()
    request = Request(scope)
    await middleware.dispatch(request, call_next)
    duration_miss = time.time() - start_time
    
    # Second call (cache hit)
    start_time = time.time()
    request = Request(scope)
    await middleware.dispatch(request, call_next)
    duration_hit = time.time() - start_time
    
    # Cache hit should be significantly faster
    assert duration_hit < duration_miss
    assert duration_hit < 0.01  # Should be near instant
    print(f"Cache miss: {duration_miss:.4f}s, Cache hit: {duration_hit:.4f}s")

@pytest.mark.asyncio
async def test_async_task_manager():
    """Test async task execution."""
    manager = AsyncTaskManager(max_workers=2)
    await manager.start()
    
    async def slow_task(seconds):
        await asyncio.sleep(seconds)
        return "done"
    
    # Submit multiple tasks
    start_time = time.time()
    tasks = []
    for _ in range(4):
        task_id = await manager.submit_task(slow_task, 0.1)
        tasks.append(task_id)
        
    # Wait for completion
    while True:
        statuses = [manager.get_task_status(tid)["status"] for tid in tasks]
        if all(s == "completed" for s in statuses):
            break
        await asyncio.sleep(0.05)
        
    duration = time.time() - start_time
    await manager.stop()
    
    # 4 tasks of 0.1s with 2 workers should take ~0.2s (plus overhead), not 0.4s
    assert duration < 0.35
    print(f"Parallel execution time: {duration:.4f}s")

if __name__ == "__main__":
    # Manual run if needed
    asyncio.run(test_cache_middleware_performance())
    asyncio.run(test_async_task_manager())
