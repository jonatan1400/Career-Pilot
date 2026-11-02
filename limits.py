"""Thread-safe anonymous hourly usage guard, with no personal data."""
import threading
import time
from collections import deque


class CoachError(RuntimeError):
    pass


class UsageLimiter:
    """Shared process quota has no student data and survives session clearing."""
    def __init__(self, hourly_limit=100):
        self.hourly_limit = hourly_limit
        self.calls = deque()
        self.lock = threading.Lock()

    def reserve(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            while self.calls and self.calls[0] <= now - 3600:
                self.calls.popleft()
            if len(self.calls) >= self.hourly_limit:
                raise CoachError('The shared hourly AI limit has been reached. Please try again later.')
            self.calls.append(now)

