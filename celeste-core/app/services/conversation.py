from __future__ import annotations

import threading
import time


class ConversationHistory:
    """Short-term, in-memory conversation memory for /assistant/chat.

    Deliberately ephemeral: it exists so follow-up turns ("y manana?",
    "cancela ese") have context, not to be a durable record like CelesteBrain
    notes. Resets after idle_seconds of inactivity or when Core restarts.
    """

    def __init__(self, max_turns: int = 6, idle_seconds: float = 1800.0):
        self.max_turns = max_turns
        self.idle_seconds = idle_seconds
        self._messages: list[dict[str, str]] = []
        self._last_activity = 0.0
        self._lock = threading.Lock()

    def recent(self) -> list[dict[str, str]]:
        with self._lock:
            self._reset_if_idle()
            return list(self._messages)

    def append_exchange(self, user_message: str, assistant_reply: str) -> None:
        user_message = user_message.strip()
        if not user_message:
            return
        with self._lock:
            self._reset_if_idle()
            self._messages.append({"role": "user", "content": user_message})
            if assistant_reply.strip():
                self._messages.append({"role": "assistant", "content": assistant_reply.strip()})
            overflow = len(self._messages) - self.max_turns * 2
            if overflow > 0:
                del self._messages[:overflow]
            self._last_activity = time.time()

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()

    def _reset_if_idle(self) -> None:
        if self._messages and time.time() - self._last_activity > self.idle_seconds:
            self._messages.clear()


conversation_history = ConversationHistory()
