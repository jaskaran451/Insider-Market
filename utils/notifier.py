# utils/notifier.py

from datetime import datetime
from typing import List, Dict, Optional


class Notifier:

    def __init__(self):
        self._queue: List[Dict] = []

    # -------------------------------------------------
    # CORE PUSH METHOD
    # -------------------------------------------------
    def push(self, message: str, level: str = "info", meta: Optional[dict] = None):

        notification = {
            "message": message,
            "level": level,   # success | error | warning | info
            "timestamp": datetime.utcnow().isoformat(),
            "meta": meta or {}
        }

        self._queue.append(notification)

        return notification

    # -------------------------------------------------
    # SHORTCUT METHODS
    # -------------------------------------------------
    def success(self, message: str, meta: dict = None):
        return self.push(message, "success", meta)

    def error(self, message: str, meta: dict = None):
        return self.push(message, "error", meta)

    def warning(self, message: str, meta: dict = None):
        return self.push(message, "warning", meta)

    def info(self, message: str, meta: dict = None):
        return self.push(message, "info", meta)

    # -------------------------------------------------
    # RETRIEVE NOTIFICATIONS (FOR UI)
    # -------------------------------------------------
    def get_all(self):
        return self._queue

    def clear(self):
        self._queue = []
notifier = Notifier()