"""Runtime self-heal for stale sessions.json routing entries (#54878).

`_prune_stale_sessions_locked` only runs at gateway startup. A session ended
in state.db while the gateway stays alive (e.g. any path that finalizes the
row without clearing sessions.json) leaves a stale `session_key -> session_id`
mapping whose session has `end_reason` set. Before this fix,
`get_or_create_session` returned that stale entry as a live routing key (it
never consulted end_reason), so every subsequent message was silently routed
into a closed session and dropped — no log, no error, no response — until the
next restart pruned it.

This is the live-gateway variant of #52804/FM9 (#52808/#54138 startup prune),
which required an actual gateway *crash*. Here the guard inside
`get_or_create_session` detects the ended row at routing time and drops the
stale entry, falling through to `_recover_session_from_db` (which reopens
`agent_close`-ended rows and resumes the SAME session_id, preserving the
transcript) or, failing recovery, to a fresh session.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from gateway.config import GatewayConfig, Platform
from gateway.session import SessionEntry, SessionSource, SessionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(key: str, session_id: str, **kw) -> SessionEntry:
    now = datetime.now()
    return SessionEntry(
        session_key=key,
        session_id=session_id,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        **kw,
    )


def _db_returning(rows: dict) -> MagicMock:
    """SessionDB mock where get_session maps session_id -> row dict."""
    db = MagicMock()
    db.get_session.side_effect = lambda sid: rows.get(sid)
    # By default recovery finds nothing (forces a fresh session).
    db.find_latest_gateway_session_for_peer.return_value = None
    db.reopen_session.return_value = None
    db.create_session.return_value = None
    # No compression continuation → the tip is the session itself (identity),
    # mirroring the real SessionDB.get_compression_tip. Without this a bare Mock
    # would return a Mock the routing heal then assigns as session_id.
    db.get_compression_tip.side_effect = lambda sid: sid
    return db


def _make_store_with_db(tmp_path, db_mock) -> SessionStore:
    """Build a SessionStore with a mock SessionDB, bypassing disk load."""
    config = GatewayConfig()
    with patch("gateway.session.SessionStore._ensure_loaded"):
        store = SessionStore(sessions_dir=tmp_path, config=config)
    store._db = db_mock
    store._loaded = True
    return store


def _source() -> SessionSource:
    # session_key for this peer is deterministic; matches the entry key we seed.
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="8494508720",
        chat_type="dm",
        user_id="8494508720",
    )


# ---------------------------------------------------------------------------
# _is_session_ended_in_db helper
# ---------------------------------------------------------------------------

class TestIsSessionEndedInDb:
    def test_ended_row_is_stale(self, tmp_path):
        db = _db_returning({"sid": {"end_reason": "agent_close", "id": "sid"}})
        store = _make_store_with_db(tmp_path, db)
        assert store._is_session_ended_in_db("sid") is True

    def test_alive_row_not_stale(self, tmp_path):
        db = _db_returning({"sid": {"end_reason": None, "id": "sid"}})
        store = _make_store_with_db(tmp_path, db)
        assert store._is_session_ended_in_db("sid") is False


# ---------------------------------------------------------------------------
# get_or_create_session — runtime self-heal
# ---------------------------------------------------------------------------

class TestRuntimeStaleGuard:

    def test_stale_ws_orphan_reap_entry_recovered_preserving_session_id(self, tmp_path):
        """Stale ``ws_orphan_reap`` entry → recovery reopens the SAME session_id (#63207)."""
        source = _source()
        db = _db_returning({"sid_stale": {"end_reason": "ws_orphan_reap", "id": "sid_stale"}})
        db.find_latest_gateway_session_for_peer.return_value = {
            "id": "sid_stale",
            "started_at": (datetime.now() - timedelta(hours=2)).timestamp(),
        }
        store = _make_store_with_db(tmp_path, db)
        key = store._generate_session_key(source)
        store._entries[key] = _make_entry(key, "sid_stale")

        result = store.get_or_create_session(source)

        assert result.session_id == "sid_stale"
        db.reopen_session.assert_called_once_with("sid_stale")
        db.create_session.assert_not_called()
        # Recovery keeps the row live — the stale_recovery bookmark must not be
        # promoted onto the reopened row (would force a fresh session next turn).
        db.promote_to_session_reset.assert_not_called()
        db.end_session.assert_not_called()


class TestRecoveredSessionActivity:
    """Recovery keeps the durable session and activity timestamp."""

    def test_recovered_entry_carries_durable_last_activity(self, tmp_path):
        """A recovered mapping reports the DB's last message time, not now()."""
        source = _source()
        started = (datetime.now() - timedelta(hours=3)).timestamp()
        last_activity = (datetime.now() - timedelta(hours=2)).timestamp()
        db = _db_returning({})
        db.find_latest_gateway_session_for_peer.return_value = {
            "id": "sid_recovered",
            "started_at": started,
            "last_activity_at": last_activity,
        }
        store = _make_store_with_db(tmp_path, db)  # default mode="none"

        result = store.get_or_create_session(source)

        assert result.session_id == "sid_recovered"
        assert result.created_at == datetime.fromtimestamp(started)
        assert result.updated_at == datetime.fromtimestamp(last_activity)
        assert result.reset_had_activity is True


    def test_recovery_resumes_unchanged(self, tmp_path):
        """Recoverable rows resume as before."""
        source = _source()
        db = _db_returning({})
        db.find_latest_gateway_session_for_peer.return_value = {
            "id": "sid_recovered",
            "started_at": (datetime.now() - timedelta(days=30)).timestamp(),
            "last_activity_at": (
                datetime.now() - timedelta(days=30)
            ).timestamp(),
        }
        store = _make_store_with_db(tmp_path, db)  # default mode="none"

        result = store.get_or_create_session(source)

        assert result.session_id == "sid_recovered"
        db.reopen_session.assert_called_once_with("sid_recovered")
        db.promote_to_session_reset.assert_not_called()
        db.end_session.assert_not_called()
        db.create_session.assert_not_called()

    def test_recovery_tolerates_row_without_last_activity(self, tmp_path):
        """A row lacking last_activity_at falls back to created_at."""
        source = _source()
        started = (datetime.now() - timedelta(hours=3)).timestamp()
        db = _db_returning({})
        db.find_latest_gateway_session_for_peer.return_value = {
            "id": "sid_recovered",
            "started_at": started,
        }
        store = _make_store_with_db(tmp_path, db)

        result = store.get_or_create_session(source)

        assert result.session_id == "sid_recovered"
        assert result.updated_at == datetime.fromtimestamp(started)
        assert result.reset_had_activity is False


class TestAdvanceCompressionSession:
    def test_cas_advances_route_without_reopening_rows(self, tmp_path):
        db = _db_returning({})
        store = _make_store_with_db(tmp_path, db)
        source = _source()
        key = store._generate_session_key(source)
        original = _make_entry(key, "sid_parent")
        store._entries[key] = original

        result = store.advance_compression_session(
            key,
            "sid_parent",
            "sid_tip",
        )

        assert result is not None
        assert result is original
        assert result.session_id == "sid_tip"
        assert store.peek_session_id(key) == "sid_tip"
        db.end_session.assert_not_called()
        db.reopen_session.assert_not_called()

    def test_repoint_does_not_touch_activity_clock(self, tmp_path):
        """Compression repoint is bookkeeping — it must not bump updated_at.

        A background compression on an idle session must not make it look
        fresh to reset policy or the restart-resume freshness gate (#85709).
        """
        db = _db_returning({})
        store = _make_store_with_db(tmp_path, db)
        source = _source()
        key = store._generate_session_key(source)
        original = _make_entry(key, "sid_parent")
        idle = datetime.now() - timedelta(days=21)
        original.updated_at = idle
        store._entries[key] = original

        result = store.advance_compression_session(key, "sid_parent", "sid_tip")

        assert result is not None
        assert result.updated_at == idle
        assert store.suspend_recently_active(max_age_seconds=120) == 0




class TestStaleRebuildCarriesContinuityHint:
    """Stale rebuild with no pending reset decision must still arm the
    continuity hint (2026-09-09 ggtms incident).

    The daily-reset finalizer ends the row in state.db at 04:00 while
    sessions.json still routes to the old id.  At the next message the
    #54878 stale guard drops the entry; `_should_reset` no longer returns a
    reason (the finalizer already consumed the daily boundary), so the fresh
    session used to be created with no `prev_session_id` — the WeCom
    continuity hint never fired and the agent answered with zero knowledge
    of the prior same-chat session, re-recommending content it had already
    given the night before.
    """

    def test_stale_session_reset_end_creates_fresh_with_continuity_metadata(
        self, tmp_path,
    ):
        source = _source()
        # end_reason=session_reset is NOT recoverable by the recovery finder
        # (only agent_close/ws_orphan_reap rows reopen), so the outcome is a
        # fresh session.  Policy mode="none" keeps `_reset_reason` empty —
        # the exact shape the fix targets.
        db = _db_returning({"sid_stale": {"end_reason": "session_reset", "id": "sid_stale"}})
        store = _make_store_with_db(tmp_path, db)
        key = store._generate_session_key(source)
        entry = _make_entry(key, "sid_stale")
        entry.last_prompt_tokens = 100  # real activity in the prior session
        store._entries[key] = entry

        result = store.get_or_create_session(source)

        # Fresh session carrying auto-reset metadata + continuity pointer.
        assert result.session_id != "sid_stale"
        assert result.was_auto_reset is True
        assert result.auto_reset_reason == "stale_recovery"
        assert result.prev_session_id == "sid_stale"
        assert result.reset_had_activity is True
        db.reopen_session.assert_not_called()
        db.create_session.assert_called_once()
        # parent_session_id records the lineage for session_search recall.
        assert db.create_session.call_args.kwargs.get("parent_session_id") == "sid_stale"

    def test_stale_recoverable_end_still_reopens_without_auto_reset(self, tmp_path):
        """Recoverable end_reason (ws_orphan_reap) → transcript preserved; the
        stale-recovery flags must NOT mark the reopened session as auto-reset."""
        source = _source()
        db = _db_returning({"sid_stale": {"end_reason": "ws_orphan_reap", "id": "sid_stale"}})
        db.find_latest_gateway_session_for_peer.return_value = {
            "id": "sid_stale",
            "started_at": (datetime.now() - timedelta(hours=2)).timestamp(),
        }
        store = _make_store_with_db(tmp_path, db)
        key = store._generate_session_key(source)
        store._entries[key] = _make_entry(key, "sid_stale")

        result = store.get_or_create_session(source)

        assert result.session_id == "sid_stale"
        assert result.was_auto_reset is False
        assert result.auto_reset_reason != "stale_recovery"
        db.reopen_session.assert_called_once_with("sid_stale")
        # Same DB-side contract as the in-memory flags: recovery succeeds, so the
        # stale_recovery bookmark must never reach promote/end (C2 regression net —
        # a MagicMock db silently no-ops promote unless asserted).
        db.promote_to_session_reset.assert_not_called()
        db.end_session.assert_not_called()


class TestStaleRecoveryRealSQLite:
    """Real-SQLite variant of the stale-recovery flow: the mock-based tests above cannot
    see ``promote_to_session_reset``'s WHERE clause, which is exactly what re-ended the
    reopened row before the bookmark fix (ended_at IS NULL matches a just-reopened row)."""

    def test_recovered_stale_row_stays_live_across_consecutive_turns(self, tmp_path):
        from hermes_state import SessionDB

        db = SessionDB(db_path=tmp_path / "state.db")
        store = _make_store_with_db(tmp_path, db)
        source = _source()

        # Production write pair: create the row through the store, then close it with a
        # recoverable end_reason while sessions.json keeps routing to it (the incident
        # shape: #61220/#61993/#63539 — agent_close row + stale routing entry).
        first = store.get_or_create_session(source)
        db.end_session(first.session_id, "agent_close")
        key = store._generate_session_key(source)
        store._entries[key] = _make_entry(key, first.session_id)

        # Turn 2 (morning): stale hit → recovery reopens the SAME session.
        second = store.get_or_create_session(source)
        assert second.session_id == first.session_id
        row = db.get_session(first.session_id)
        assert row["end_reason"] is None

        # Turn 3: the recovered session must keep routing — pre-fix, promote re-ended the
        # row as 'stale_recovery' (unrecoverable) and this call forced a fresh session.
        third = store.get_or_create_session(source)
        assert third.session_id == first.session_id
        assert db.get_session(first.session_id)["end_reason"] is None
        db.close()
