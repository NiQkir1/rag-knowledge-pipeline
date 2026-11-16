"""
Circuit Breaker Pattern for LLM & Embedding External Services
Предотвращает каскадные сбои при деградации внешних провайдеров (OpenAI, Anthropic, Triton).
Состояния: CLOSED (норма), OPEN (сбой, запросы сразу перенаправляются на фолбэк), HALF-OPEN (тестовая проверка).
"""

import time
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger("circuit-breaker")

class CircuitBreakerOpenException(Exception):
    """Исключение, если контур открыт и сервис временно заблокирован"""
    pass

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_time_seconds: float = 30.0,
        name: str = "ExternalService"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time_seconds
        self.name = name
        
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable, fallback_func: Optional[Callable] = None, *args, **kwargs) -> Any:
        current_time = time.time()

        # Проверка перехода из OPEN в HALF-OPEN
        if self.state == "OPEN":
            if current_time - self.last_failure_time >= self.recovery_time:
                logger.info(f"[{self.name}] Recovery timeout expired. Switching to HALF-OPEN to probe service.")
                self.state = "HALF_OPEN"
            else:
                logger.warning(f"[{self.name}] Circuit is OPEN. Triggering fallback.")
                if fallback_func:
                    return fallback_func(*args, **kwargs)
                raise CircuitBreakerOpenException(f"[{self.name}] Service temporarily unavailable (Circuit OPEN)")

        try:
            result = func(*args, **kwargs)
            # Успешный вызов
            if self.state == "HALF_OPEN":
                logger.info(f"[{self.name}] Probe succeeded! Circuit recovered to CLOSED.")
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = current_time
            logger.error(f"[{self.name}] Call failed ({self.failure_count}/{self.failure_threshold}): {e}")

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.critical(f"[{self.name}] Failure threshold reached! Circuit switched to OPEN.")

            if fallback_func:
                logger.info(f"[{self.name}] Executing fallback routine.")
                return fallback_func(*args, **kwargs)
            raise e
