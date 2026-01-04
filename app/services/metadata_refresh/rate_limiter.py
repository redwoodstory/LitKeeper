import time
import threading
from typing import Optional


class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def _refill_tokens(self) -> None:
        now = time.time()
        elapsed = now - self.last_update
        
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_update = now
    
    def wait_if_needed(self) -> None:
        with self.lock:
            self._refill_tokens()
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.time_window / self.max_requests)
                time.sleep(wait_time)
                self._refill_tokens()
            
            self.tokens -= 1
    
    def get_available_tokens(self) -> float:
        with self.lock:
            self._refill_tokens()
            return self.tokens
