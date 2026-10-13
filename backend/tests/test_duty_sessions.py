"""Tests for duty-shift sessions: the new session_kind="duty" tag on
share_sessions (app/repositories/share_session_repository.py) and the
join/resume/end/status orchestration in
app/services/duty_session_service.py.

Same philosophy as test_share.py: mongomock-backed repositories swapped
into module singletons via monkeypatch, no unittest.mock.

Run from backend/: pytest tests/test_duty_sessions.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.share_tokens import issue_token  # noqa: E402
from app.repositories.share_session_repository import (  # noqa: E402
    SESSION_KIND_DISPATCH,
    SESSION_KIND_DUTY,
    STATUS_ACTIVE,
    STATUS_PENDING,
    ShareSessionRepository,
)
from app.services.duty_session_service import (  # noqa: E402
    end_duty_session,
    get_duty_status,
    start_or_resume_duty_session,
)

TEST_SETTINGS = Settings(
    SHARE_SECRET_KEY="test-secret-key-for-duty-sessions",
    SHARE_INVITE_TTL_SECONDS=900,
    SHARE_SESSION_MAX_DURATION_SECONDS=7200,
    PUBLIC_BASE_URL="https://example.ngrok.app",
)


@pytest.fixture()
def share_repo() -> ShareSessionRepository:
    db = mongomock.MongoClient()["sentinel_x_test"]
    return ShareSessionRepository(db)


# ---------------------------------------------------------------------------
# share_session_repository.py: session_kind + the two new read methods
# ---------------------------------------------------------------------------


def test_create_defaults_to_dispatch_kind(share_repo):
    """Existing call sites (app/api/routes/dispatch.py) pass no
    session_kind -- behavior must be unchanged (default "dispatch")."""
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id="job-1",
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
    )
    assert doc["session_kind"] == SESSION_KIND_DISPATCH


def test_create_duty_session_has_no_dispatch_id(share_repo):
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id=None,
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
        session_kind=SESSION_KIND_DUTY,
    )
    assert doc["session_kind"] == SESSION_KIND_DUTY
    assert doc["dispatch_id"] is None
    assert doc["status"] == STATUS_PENDING


def test_get_active_duty_session_finds_pending(share_repo):
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id=None,
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
        session_kind=SESSION_KIND_DUTY,
    )
    found = share_repo.get_active_duty_session_for_responder("r1")
    assert found is not None
    assert found["session_id"] == doc["session_id"]


def test_get_active_duty_session_ignores_dispatch_sessions(share_repo):
    """A responder with an active *dispatch* share session (unrelated to
    duty) must not look like they have a duty session."""
    share_repo.create(
        responder_id="r1",
        dispatch_id="job-1",
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
    )
    assert share_repo.get_active_duty_session_for_responder("r1") is None


def test_get_active_duty_session_none_when_stopped(share_repo):
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id=None,
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
        session_kind=SESSION_KIND_DUTY,
    )
    share_repo.mark_stopped(doc["session_id"])
    assert share_repo.get_active_duty_session_for_responder("r1") is None


def test_list_active_duty_sessions_excludes_pending(share_repo):
    """A responder who joined but never opened the link / pressed Start
    (still "pending") must be excluded from the auto-dispatch candidate
    pool -- they have no real location to dispatch against."""
    share_repo.create(
        responder_id="r1",
        dispatch_id=None,
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
        session_kind=SESSION_KIND_DUTY,
    )
    assert share_repo.list_active_duty_sessions() == []


def test_list_active_duty_sessions_includes_active(share_repo):
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id=None,
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
        session_kind=SESSION_KIND_DUTY,
    )
    share_repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    active = share_repo.list_active_duty_sessions()
    assert len(active) == 1
    assert active[0]["session_id"] == doc["session_id"]
    assert active[0]["status"] == STATUS_ACTIVE


def test_list_active_duty_sessions_excludes_dispatch_kind(share_repo):
    doc, _token = share_repo.create(
        responder_id="r1",
        dispatch_id="job-1",
        invite_ttl_seconds=900,
        token_factory=lambda sid, rid: issue_token(sid, rid, TEST_SETTINGS),
    )
    share_repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    assert share_repo.list_active_duty_sessions() == []


# ---------------------------------------------------------------------------
# duty_session_service.py: join / resume / end / status orchestration
# ---------------------------------------------------------------------------


def test_start_duty_session_creates_a_pending_session_with_a_link(share_repo):
    result = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert result.resumed is False
    assert result.status == STATUS_PENDING
    assert result.share_url is not None
    assert result.share_url.startswith(TEST_SETTINGS.PUBLIC_BASE_URL)


def test_start_duty_session_twice_is_idempotent(share_repo):
    """Sending "join" twice must resume the same session, not create a
    second one."""
    first = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    second = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert second.resumed is True
    assert second.session_id == first.session_id
    # Resumed sessions never fabricate a new link -- the raw token is
    # never stored, so there is nothing real to hand back here.
    assert second.share_url is None


def test_start_duty_session_resumes_an_active_session_too(share_repo):
    first = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    share_repo.mark_active(first.session_id, responder_id="r1", active_duration_seconds=7200)
    second = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert second.resumed is True
    assert second.session_id == first.session_id
    assert second.status == STATUS_ACTIVE


def test_different_responders_get_independent_duty_sessions(share_repo):
    r1 = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    r2 = start_or_resume_duty_session("r2", settings=TEST_SETTINGS, share_repo=share_repo)
    assert r1.session_id != r2.session_id


def test_end_duty_session_stops_an_active_session(share_repo):
    joined = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    share_repo.mark_active(joined.session_id, responder_id="r1", active_duration_seconds=7200)

    result = end_duty_session("r1", share_repo=share_repo)
    assert result.stopped is True
    assert result.session_id == joined.session_id
    assert share_repo.get_active_duty_session_for_responder("r1") is None


def test_end_duty_session_with_no_session_is_a_harmless_noop(share_repo):
    result = end_duty_session("r1", share_repo=share_repo)
    assert result.stopped is False
    assert result.session_id is None


def test_end_duty_session_twice_is_idempotent(share_repo):
    joined = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    first_end = end_duty_session("r1", share_repo=share_repo)
    second_end = end_duty_session("r1", share_repo=share_repo)
    assert first_end.stopped is True
    assert second_end.stopped is False  # nothing left to stop -- not an error
    assert second_end.session_id is None


def test_end_duty_session_preserves_last_known_location(share_repo):
    """Ending duty must not erase the session's last recorded position --
    mark_stopped only ever changes `status`."""
    joined = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    share_repo.mark_active(joined.session_id, responder_id="r1", active_duration_seconds=7200)
    share_repo.record_update(joined.session_id, latitude=12.34, longitude=56.78, accuracy_meters=5.0)

    end_duty_session("r1", share_repo=share_repo)

    doc = share_repo.get(joined.session_id)
    assert doc["status"] == "stopped"
    assert doc["last_lat"] == 12.34
    assert doc["last_lng"] == 56.78


def test_get_duty_status_reports_no_session(share_repo):
    status = get_duty_status("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert status.has_duty_session is False
    assert status.status is None


def test_get_duty_status_reports_pending(share_repo):
    start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    status = get_duty_status("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert status.has_duty_session is True
    assert status.status == STATUS_PENDING
    # Never fabricates a link on a status check either.
    assert status.share_url is None


def test_get_duty_status_reports_active(share_repo):
    joined = start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    share_repo.mark_active(joined.session_id, responder_id="r1", active_duration_seconds=7200)
    status = get_duty_status("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert status.status == STATUS_ACTIVE


def test_get_duty_status_after_end_reports_no_session(share_repo):
    start_or_resume_duty_session("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    end_duty_session("r1", share_repo=share_repo)
    status = get_duty_status("r1", settings=TEST_SETTINGS, share_repo=share_repo)
    assert status.has_duty_session is False
