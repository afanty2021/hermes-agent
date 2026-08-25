"""
Circuit-breaker reachability classification for MCP tool calls.

Incident 2026-08-24: four identity-lock refusals (JSON-RPC -32602) from the
llm-wiki MCP server tripped the "unreachable" circuit breaker, which then
blocked the next legitimate call (plan_create) with a false "server is
unreachable / still recovering" message — while searches were succeeding on
the very same server seconds earlier.

These tests pin the fix: only transport-level failures (no protocol response
from the server) may burn breaker strikes. Anything the server *answered* —
a JSON-RPC error (McpError) or an isError tool result — proves reachability
and resets the breaker instead.
"""

import asyncio

import pytest

from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ErrorData, TextContent

from tools import mcp_tool


SERVER = "llm-wiki-training"
TOOL = "llm_wiki_read_file"


@pytest.fixture(autouse=True)
def _clean_breaker_state():
    mcp_tool._server_error_counts.clear()
    mcp_tool._server_breaker_opened_at.clear()
    yield
    mcp_tool._server_error_counts.clear()
    mcp_tool._server_breaker_opened_at.clear()


class _FakeSession:
    def __init__(self, outcome):
        self._outcome = outcome

    async def call_tool(self, name, arguments=None, meta=None, **kwargs):
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class _FakeServer:
    def __init__(self, outcome):
        self.session = _FakeSession(outcome)
        self._rpc_lock = asyncio.Lock()

    # mark_tool_call intentionally absent — the handler must tolerate that.


def _install(monkeypatch, outcome):
    server = _FakeServer(outcome)
    monkeypatch.setattr(mcp_tool, "_trust_gate_check", lambda s, t: None)
    monkeypatch.setattr(mcp_tool, "_get_connected_server_for_call", lambda s: server)

    def _run(coro_or_factory, timeout=None):
        # Real _run_on_mcp_loop accepts a coroutine or a zero-arg factory.
        coro = coro_or_factory() if callable(coro_or_factory) else coro_or_factory
        return asyncio.run(coro)

    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", _run)
    return mcp_tool._make_tool_handler(SERVER, TOOL, 5.0)


IDENTITY_REFUSAL = McpError(ErrorData(
    code=-32602,
    message='wecom_userid "Huangzhengbo" does not match session identity '
            '"TuoMaSiXueXiGuanGuangGuLanGuangX": refusing call '
            '(session identity is locked; no override, no retry)',
))


def test_classifier_accepts_jsonrpc_error_response():
    assert mcp_tool._is_application_level_mcp_error(IDENTITY_REFUSAL)


def test_classifier_rejects_transport_errors():
    assert not mcp_tool._is_application_level_mcp_error(ConnectionError("refused"))
    assert not mcp_tool._is_application_level_mcp_error(TimeoutError("timed out"))
    assert not mcp_tool._is_application_level_mcp_error(RuntimeError("boom"))


def test_classifier_rejects_mcp_error_without_code():
    bare = McpError.__new__(McpError)  # constructed without .error payload
    assert not mcp_tool._is_application_level_mcp_error(bare)


def test_identity_refusals_never_trip_the_breaker(monkeypatch):
    """The exact incident shape: many -32602 refusals in a row must leave
    the breaker closed so the next tool on the same server still runs."""
    handler = _install(monkeypatch, IDENTITY_REFUSAL)
    for _ in range(5):
        result = handler({})
        assert "does not match session identity" in result
    assert mcp_tool._server_error_counts.get(SERVER, 0) == 0


def test_is_error_results_do_not_burn_the_breaker(monkeypatch):
    """An isError tool result is a completed, answered RPC (e.g. bad args,
    not found) — reachability proven, no strike."""
    result_obj = CallToolResult(
        content=[TextContent(type="text", text="boom: bad arguments")],
        isError=True,
    )
    handler = _install(monkeypatch, result_obj)
    for _ in range(5):
        out = handler({})
        assert "bad arguments" in out
    assert mcp_tool._server_error_counts.get(SERVER, 0) == 0


def test_transport_failures_still_trip_the_breaker(monkeypatch):
    """Regression guard: a genuinely dead transport still trips the breaker
    after the configured number of consecutive failures (#10447)."""
    handler = _install(monkeypatch, ConnectionError("[Errno 61] Connection refused"))
    for _ in range(mcp_tool._CIRCUIT_BREAKER_THRESHOLD):
        handler({})
    assert mcp_tool._server_error_counts[SERVER] == mcp_tool._CIRCUIT_BREAKER_THRESHOLD
    blocked = handler({})
    assert "unreachable after" in blocked
    assert "consecutive" in blocked


SYNTHETIC_408 = McpError(ErrorData(
    code=408,
    message="Timed out while waiting for response to CallToolRequest. "
            "Waited 30.0 seconds.",
))


def test_synthetic_timeout_408_still_bumps():
    """SDK landmine (mcp 1.26.0): with read_timeout_seconds configured the
    CLIENT converts its own TimeoutError into McpError(408) — no server
    response involved. A hung server must keep burning strikes (and trip),
    exactly like a refused one."""
    assert not mcp_tool._is_application_level_mcp_error(SYNTHETIC_408)


def test_hung_server_via_408_trips_the_breaker(monkeypatch):
    handler = _install(monkeypatch, SYNTHETIC_408)
    for _ in range(mcp_tool._CIRCUIT_BREAKER_THRESHOLD):
        handler({})
    assert mcp_tool._server_error_counts[SERVER] == mcp_tool._CIRCUIT_BREAKER_THRESHOLD
    assert "unreachable after" in handler({})


def test_app_level_error_resets_prior_transport_strikes(monkeypatch):
    """Mixed scenario pins the reset-to-zero semantics: 2 real transport
    failures, then one answered -32602 (identity refusal) proves the server
    is alive and fully closes the breaker — the next 2 transport failures
    alone must NOT trip it (would have if strikes were merely preserved).
    (_install patches module-level globals, so each phase swaps the fake
    server; earlier handlers stay valid — they resolve globals at call
    time.)"""
    def transport():
        return _install(monkeypatch, ConnectionError("refused"))

    def refusal():
        return _install(monkeypatch, IDENTITY_REFUSAL)

    transport()({})
    transport()({})
    assert mcp_tool._server_error_counts[SERVER] == 2

    refusal()({})
    assert mcp_tool._server_error_counts.get(SERVER, 0) == 0, (
        "an answered JSON-RPC error must reset the consecutive-failure count"
    )

    transport()({})
    transport()({})
    assert mcp_tool._server_error_counts[SERVER] == 2, (
        "after reset, 2 strikes alone must not reach the threshold of "
        f"{mcp_tool._CIRCUIT_BREAKER_THRESHOLD}"
    )
    assert "unreachable after" not in refusal()({})
