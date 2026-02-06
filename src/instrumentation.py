"""
Instrumentation decorators for Strands agents.
"""

import time
import functools
import logging
from typing import Callable, Any
from src.metrics import (
    AGENT_EXECUTION_TIME,
    AGENT_SUCCESS_RATE,
    AGENT_CONFIDENCE_SCORE
)

logger = logging.getLogger(__name__)

def instrument_agent(agent_name: str):
    """
    Decorator to instrument agent execution methods.
    
    Tracks:
    - Execution time
    - Success/Failure counts
    - Confidence scores (if returned)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                
                # Try to extract confidence score if result is a dict or object
                confidence = 0.0
                if isinstance(result, dict) and "confidence" in result:
                    confidence = float(result["confidence"])
                elif hasattr(result, "confidence"):
                    confidence = float(result.confidence)
                
                if confidence > 0:
                    AGENT_CONFIDENCE_SCORE.labels(agent_name=agent_name).observe(confidence)
                
                return result
                
            except Exception as e:
                status = "failure"
                logger.error(f"Agent {agent_name} failed: {e}")
                raise e
                
            finally:
                duration = time.time() - start_time
                AGENT_EXECUTION_TIME.labels(agent_name=agent_name, status=status).observe(duration)
                AGENT_SUCCESS_RATE.labels(agent_name=agent_name, status=status).inc()
                
        return wrapper
    return decorator
