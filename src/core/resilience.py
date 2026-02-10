"""
Resilience Layer - Circuit Breaker, Retry, Timeout

Implementa padrões de resiliência enterprise para chamadas a sistemas externos.
"""

import logging
import time
from typing import Callable, TypeVar, Any, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta
from functools import wraps
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Estados do circuit breaker."""
    CLOSED = "CLOSED"           # Normal, permitindo requisições
    OPEN = "OPEN"               # Falhas detectadas, bloqueando requisições
    HALF_OPEN = "HALF_OPEN"     # Testando se o serviço se recuperou


class CircuitBreakerMetrics:
    """Métricas do circuit breaker."""
    
    def __init__(self):
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.state_changes = []
    
    def record_success(self):
        self.total_calls += 1
        self.successful_calls += 1
        self.last_success_time = datetime.now(timezone.utc)
    
    def record_failure(self):
        self.total_calls += 1
        self.failed_calls += 1
        self.last_failure_time = datetime.now(timezone.utc)
    
    def record_rejection(self):
        self.rejected_calls += 1
    
    def record_state_change(self, old_state: CircuitState, new_state: CircuitState):
        self.state_changes.append({
            "timestamp": datetime.now(timezone.utc),
            "from": old_state.value,
            "to": new_state.value
        })
    
    def get_failure_rate(self) -> float:
        """Retorna taxa de falha (0.0 a 1.0)."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": self.get_failure_rate(),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "state_changes": self.state_changes
        }


class CircuitBreaker:
    """
    Circuit breaker para proteger chamadas a sistemas externos.
    
    Padrão: CLOSED → OPEN → HALF_OPEN → CLOSED
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.metrics = CircuitBreakerMetrics()
        self._lock = threading.Lock()
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Executa função através do circuit breaker."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._change_state(CircuitState.HALF_OPEN)
                    logger.info(f"[{self.name}] Circuit breaker transitioning to HALF_OPEN")
                else:
                    self.metrics.record_rejection()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar recuperação."""
        if not self.last_failure_time:
            return False
        
        elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout_seconds
    
    def _on_success(self):
        """Registra sucesso."""
        with self._lock:
            self.metrics.record_success()
            if self.state == CircuitState.HALF_OPEN:
                self._change_state(CircuitState.CLOSED)
                logger.info(f"[{self.name}] Circuit breaker recovered. Transitioning to CLOSED")
            self.failure_count = 0
    
    def _on_failure(self):
        """Registra falha."""
        with self._lock:
            self.metrics.record_failure()
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)
            
            if self.failure_count >= self.failure_threshold:
                self._change_state(CircuitState.OPEN)
                logger.warning(
                    f"[{self.name}] Circuit breaker opened after {self.failure_count} failures"
                )
    
    def _change_state(self, new_state: CircuitState):
        """Muda estado do circuit breaker."""
        old_state = self.state
        self.state = new_state
        self.metrics.record_state_change(old_state, new_state)
    
    def get_status(self) -> dict:
        """Retorna status atual do circuit breaker."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "metrics": self.metrics.to_dict()
        }


class CircuitBreakerOpenError(Exception):
    """Exceção quando circuit breaker está aberto."""
    pass


class RetryConfig:
    """Configuração de retry com backoff exponencial."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calcula delay para tentativa (com backoff exponencial)."""
        import random
        
        delay = min(
            self.initial_delay_seconds * (self.exponential_base ** attempt),
            self.max_delay_seconds
        )
        
        if self.jitter:
            # Adicionar jitter (±20%)
            jitter_amount = delay * 0.2
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator para retry com backoff exponencial.
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}. "
                            f"Retrying in {delay:.2f}s. Error: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}. "
                            f"Final error: {str(e)}"
                        )
            
            raise last_exception
        
        return wrapper
    
    return decorator


def timeout(seconds: float):
    """
    Decorator para timeout em chamadas.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
            
            # Configurar signal (Unix only)
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(seconds))
                
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                
                return result
            except (AttributeError, ValueError):
                # Windows ou ambiente sem signal support
                # Fallback: executar sem timeout
                logger.warning(f"Timeout decorator not supported on this platform. Running {func.__name__} without timeout.")
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class ResilienceContext:
    """
    Contexto de resiliência que combina circuit breaker, retry e timeout.
    """
    
    def __init__(
        self,
        name: str,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.name = name
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name)
        self.retry_config = retry_config or RetryConfig()
        self.timeout_seconds = timeout_seconds or 30.0
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Executa função com resiliência completa:
        1. Verifica circuit breaker
        2. Aplica retry com backoff
        3. Aplica timeout
        """
        @retry_with_backoff(self.retry_config)
        @timeout(self.timeout_seconds)
        def _wrapped():
            return self.circuit_breaker.call(func, *args, **kwargs)
        
        return _wrapped()
    
    def get_status(self) -> dict:
        """Retorna status de resiliência."""
        return {
            "name": self.name,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "retry_config": {
                "max_attempts": self.retry_config.max_attempts,
                "initial_delay": self.retry_config.initial_delay_seconds,
                "max_delay": self.retry_config.max_delay_seconds
            },
            "timeout_seconds": self.timeout_seconds
        }
