"""Tests for SessionStore — TTL, ownership, capacity."""

from __future__ import annotations

import time

import pytest

from fos_ai.schemas_chat import ChatMessage, ChatSession
from fos_ai.services.session_store import SessionStore, SessionStoreFull


def test_create_session_assigns_uuid_and_user():
    store = SessionStore()
    s = store.create(user_id=7)
    assert s.user_id == 7
    assert len(s.session_id) == 36  # uuid4 canonical
    assert s.messages == []
    assert len(store) == 1


def test_get_returns_session_for_owner():
    store = SessionStore()
    s = store.create(user_id=7)
    fetched = store.get(s.session_id, user_id=7)
    assert fetched is not None
    assert fetched.session_id == s.session_id


def test_get_rejects_other_user():
    store = SessionStore()
    s = store.create(user_id=7)
    assert store.get(s.session_id, user_id=8) is None


def test_get_unknown_returns_none():
    store = SessionStore()
    assert store.get("nope", user_id=1) is None


def test_get_or_create_reuses_valid_session():
    store = SessionStore()
    s1 = store.create(user_id=7)
    s2 = store.get_or_create(s1.session_id, user_id=7)
    assert s1.session_id == s2.session_id
    assert len(store) == 1


def test_get_or_create_mints_new_when_session_id_missing():
    store = SessionStore()
    s1 = store.create(user_id=7)
    s2 = store.get_or_create(None, user_id=7)
    assert s1.session_id != s2.session_id
    assert len(store) == 2


def test_get_or_create_mints_new_when_unknown_id():
    store = SessionStore()
    s = store.get_or_create("does-not-exist", user_id=7)
    assert s.session_id != "does-not-exist"
    assert len(store) == 1


def test_ttl_expiry():
    store = SessionStore(ttl_seconds=1)
    s = store.create(user_id=7)
    assert store.get(s.session_id, user_id=7) is not None
    time.sleep(1.1)
    assert store.get(s.session_id, user_id=7) is None
    assert len(store) == 0


def test_save_updates_messages():
    store = SessionStore()
    s = store.create(user_id=7)
    s.append(ChatMessage(role="user", content=[{"type": "text", "text": "hi"}]))
    store.save(s)
    fetched = store.get(s.session_id, user_id=7)
    assert fetched is not None
    assert len(fetched.messages) == 1
    assert fetched.messages[0].role == "user"


def test_delete():
    store = SessionStore()
    s = store.create(user_id=7)
    assert store.delete(s.session_id) is True
    assert len(store) == 0
    assert store.delete(s.session_id) is False


def test_evict_expired_returns_count():
    store = SessionStore(ttl_seconds=1, max_sessions=10)
    store.create(user_id=1)
    store.create(user_id=2)
    time.sleep(1.1)
    # direct evict call — two should go
    removed = store.evict_expired()
    assert removed == 2
    assert len(store) == 0


def test_capacity_limit_raises():
    store = SessionStore(max_sessions=2)
    store.create(user_id=1)
    store.create(user_id=2)
    with pytest.raises(SessionStoreFull):
        store.create(user_id=3)


def test_capacity_reclaimed_after_expiry():
    store = SessionStore(ttl_seconds=1, max_sessions=2)
    store.create(user_id=1)
    store.create(user_id=2)
    time.sleep(1.1)
    # Old ones should auto-evict during create()
    s3 = store.create(user_id=3)
    assert s3.user_id == 3
    assert len(store) == 1


def test_touch_extends_lifetime():
    store = SessionStore(ttl_seconds=1)
    s = store.create(user_id=7)
    time.sleep(0.6)
    # access resets last_active_at via get()
    store.get(s.session_id, user_id=7)
    time.sleep(0.6)
    # total elapsed 1.2s but last access was 0.6s ago
    assert store.get(s.session_id, user_id=7) is not None


def test_chat_session_append_updates_last_active():
    s = ChatSession.new(user_id=7)
    t0 = s.last_active_at
    time.sleep(0.01)
    s.append(ChatMessage(role="user", content=[{"type": "text", "text": "x"}]))
    assert s.last_active_at > t0
    assert len(s.messages) == 1
