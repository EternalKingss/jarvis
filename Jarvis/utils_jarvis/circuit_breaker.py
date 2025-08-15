import time
class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int = 3, recovery_time: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = 0.0

    def _record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time < self.recovery_time:
                raise RuntimeError("Circuit breaker is open")
            # allow trial request
            self.state = "HALF"
        try:
            result = func(*args, **kwargs)
        except Exception:
            self._record_failure()
            raise
        else:
            if self.state in ["OPEN", "HALF"]:
                self.state = "CLOSED"
                self.failure_count = 0
            return result
