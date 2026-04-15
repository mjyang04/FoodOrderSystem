"""In-memory chat session store with TTL eviction.

Server restart loses sessions — acceptable for demo. A production deployment
would swap this for Redis with the same interface.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Iterator

from fos_ai.schemas_chat import ChatSession

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 30 * 60  # 30 minutes
_DEFAULT_MAX_SESSIONS = 1000


class SessionStoreFull(RuntimeError):
    """Raised when max_sessions is reached and no idle session can be evicted."""


class SessionStore:
    """Thread-safe `session_id -> ChatSession` map with idle-TTL expiry."""

    def __init__(
        self,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_sessions: int = _DEFAULT_MAX_SESSIONS,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._lock = threading.Lock()
        self._sessions: dict[str, ChatSession] = {}

    # ---- core operations ----

    def create(self, user_id: int) -> ChatSession:
        """Mint a new session. Raises SessionStoreFull if at capacity."""
        with self._lock:
            self._evict_expired_locked()
            if len(self._sessions) >= self._max:
                raise SessionStoreFull(
                    f"SessionStore at capacity ({self._max})"
                )
            session = ChatSession.new(user_id=user_id)
            self._sessions[session.session_id] = session
            logger.debug(
                "session created: id=%s user=%d total=%d",
                session.session_id, user_id, len(self._sessions),
            )
            return session

    def get(self, session_id: str, user_id: int) -> ChatSession | None:
        """Fetch a session if it exists, not expired, and owned by user_id."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.user_id != user_id:
                # ownership mismatch — treat as not-found to avoid leaks
                return None
            if self._is_expired_locked(session):
                self._sessions.pop(session_id, None)
                return None
            session.touch()
            return session

    def get_or_create(self, session_id: str | None, user_id: int) -> ChatSession:
        """Return existing session if valid, otherwise mint a new one."""
        if session_id:
            existing = self.get(session_id, user_id)
            if existing is not None:
                return existing
        return self.create(user_id)

    def save(self, session: ChatSession) -> None:
        """Persist updates to an existing session."""
        with self._lock:
            session.touch()
            self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    # ---- introspection ----

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            return iter(list(self._sessions.keys()))

    def evict_expired(self) -> int:
        """Manually trigger eviction — returns count removed."""
        with self._lock:
            return self._evict_expired_locked()

    # ---- internals ----

    def _is_expired_locked(self, session: ChatSession) -> bool:
        return (time.time() - session.last_active_at) > self._ttl

    def _evict_expired_locked(self) -> int:
        expired = [
            sid for sid, s in self._sessions.items()
            if self._is_expired_locked(s)
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
        if expired:
            logger.info("evicted %d expired sessions", len(expired))
        return len(expired)
