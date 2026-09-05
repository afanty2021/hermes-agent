"""zops vendor chain pin-tests (Lan-WinRm 评审一 C3/C1 收口, 2026-09-05).

Pins the message-id chain that zops-mcp plan-confirm depends on, and the
weCom-shaped credential fingerprint behavior:

1. 0004 pin — WeComAdapter._on_message MUST pass ``message_id`` into
   build_source. Regression (dropped kwarg) is silent upstream but fatal
   downstream: zops-mcp fail-closes every execution-class tool
   ("缺少会话消息标识 hermes_message_id").
2. 0002 pin — session ContextVar ``message_id`` MUST be exported as
   ``hermes_message_id`` in tools/call ``_meta`` (and absent when unset).
   The upstream TestSessionMetaIdentity covers the other six keys but
   never exercised message_id.
3. fingerprint pin — WeCom adapters fingerprint by ``_bot_id`` (identity),
   so duplicate-profile detection works for the actual race hazard (two
   profiles claiming the same bot), independent of the secret text.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.session_context import clear_session_vars, set_session_vars


# =====================================================================
# WeCom _on_message → build_source(message_id=...)  (0004 pin)
# =====================================================================

def _make_wecom_adapter(captured):
    """Minimal WeComAdapter via object.__new__ (same pattern as
    tests/gateway/test_text_batching.py) with just enough for _on_message
    on a voice-type payload (voice skips text batching → direct dispatch)."""
    from plugins.platforms.wecom.adapter import WeComAdapter

    def fake_build_source(**kw):
        captured.update(kw)
        from gateway.platforms.base import SessionSource

        return SessionSource(
            platform=Platform.WECOM,
            chat_id=kw.get("chat_id") or "",
            chat_type=kw.get("chat_type") or "dm",
            message_id=kw.get("message_id"),
            user_id=kw.get("user_id"),
            user_name=kw.get("user_name"),
        )

    config = PlatformConfig(enabled=True, token="test-token")
    adapter = object.__new__(WeComAdapter)
    adapter._platform = Platform.WECOM
    adapter.platform = Platform.WECOM  # name property 读 self.platform.value
    adapter.config = config
    adapter._pending_text_batches = {}
    adapter._pending_text_batch_tasks = {}
    adapter._text_batch_delay_seconds = 0.05
    adapter._text_batch_split_delay_seconds = 0.1
    adapter._active_sessions = {}
    adapter._pending_messages = {}
    adapter._message_handler = AsyncMock()
    adapter._dedup = SimpleNamespace(is_duplicate=lambda mid: False)
    adapter._group_chat_ids = set()
    adapter._group_policy = "open"
    adapter._is_group_allowed = lambda chat_id, sender_id: True
    adapter._is_dm_intake_allowed = lambda sender_id: True
    adapter._remember_reply_req_id = lambda *a, **k: None
    adapter._remember_chat_req_id = lambda *a, **k: None
    adapter._payload_req_id = lambda payload: None
    adapter.build_source = fake_build_source
    adapter.handle_message = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_wecom_on_message_passes_message_id_to_build_source():
    captured = {}
    adapter = _make_wecom_adapter(captured)
    payload = {
        "body": {
            "msgid": "m-123",
            "chattype": "single",
            "from": {"userid": "teacher1"},
            "msgtype": "voice",
            "voice": {"content": "把文件传到 writingroom"},
        }
    }

    await adapter._on_message(payload)

    assert captured.get("message_id") == "m-123", (
        "0004 regression: build_source called without message_id — "
        "zops-mcp would fail-close every execution-class tool"
    )
    # WeCom 把附件/语音也走 pending-batch 合并——合并后事件保留首片 message_id
    # （0004 头注"文本批处理合并语义"的机器钉）。
    await asyncio.sleep(0.2)
    assert adapter.handle_message.await_count == 1
    assert adapter.handle_message.await_args[0][0].message_id == "m-123"


@pytest.mark.asyncio
async def test_wecom_on_message_falls_back_to_req_id_when_msgid_missing():
    """msgid 缺失时回落 req_id（_payload_req_id）——回落值同样必须进 build_source。"""
    captured = {}
    adapter = _make_wecom_adapter(captured)
    adapter._payload_req_id = lambda payload: "req-456"
    payload = {
        "body": {
            "chattype": "single",
            "from": {"userid": "teacher1"},
            "msgtype": "voice",
            "voice": {"content": "hello"},
        }
    }

    await adapter._on_message(payload)

    assert captured.get("message_id") == "req-456"


# =====================================================================
# session ContextVar → _meta export  (0002 pin)
# =====================================================================

def test_session_message_id_exported_to_meta():
    from tools.mcp_tool import _build_session_meta

    tokens = set_session_vars(
        platform="wecom",
        user_id="teacher1",
        profile="zops",
        message_id="m-123",
    )
    try:
        meta = _build_session_meta()
        assert meta["hermes_message_id"] == "m-123"
        assert meta["hermes_profile"] == "zops"
    finally:
        clear_session_vars(tokens)


def test_meta_drops_message_id_when_unset():
    """message_id 未绑定 → 键整体缺失（falsy 被丢），不会出现空串键。"""
    from tools.mcp_tool import _build_session_meta

    tokens = set_session_vars(platform="wecom", user_id="teacher1", profile="zops")
    try:
        meta = _build_session_meta()
        assert "hermes_message_id" not in meta
    finally:
        clear_session_vars(tokens)


# =====================================================================
# credential fingerprint — wecom shape  (评审一 C1 行为钉)
# =====================================================================

class _WecomShapeAdapter:
    """attr 形态对齐 WeComAdapter（_bot_id/_secret），供指纹函数消费。"""

    def __init__(self, bot_id, secret):
        self._bot_id = bot_id
        self._secret = secret


class TestWecomCredentialFingerprint:
    def test_same_bot_id_different_secret_same_fingerprint(self):
        from gateway.run import GatewayRunner

        fp_a = GatewayRunner._adapter_credential_fingerprint(
            _WecomShapeAdapter("botB", "secret-X"))
        fp_b = GatewayRunner._adapter_credential_fingerprint(
            _WecomShapeAdapter("botB", "secret-Y"))
        assert fp_a is not None
        # 同一 bot_id = 同一个企微机器人 = 同 bot WS 竞争风险 → 必须同指纹可检出；
        # secret 文本不参与（身份指纹非凭据指纹，typo secret 的克隆同样要被点名）。
        assert fp_a == fp_b

    def test_different_bot_id_different_fingerprint(self):
        from gateway.run import GatewayRunner

        fp_a = GatewayRunner._adapter_credential_fingerprint(
            _WecomShapeAdapter("botA", "secret-X"))
        fp_b = GatewayRunner._adapter_credential_fingerprint(
            _WecomShapeAdapter("botB", "secret-X"))
        assert fp_a != fp_b  # 两个不同机器人，各自 WS 无竞争，不该误报

    def test_fingerprint_is_log_safe_hash(self):
        from gateway.run import GatewayRunner

        fp = GatewayRunner._adapter_credential_fingerprint(
            _WecomShapeAdapter("botA", "secret-X"))
        assert fp and len(fp) == 16 and "botA" not in fp and "secret-X" not in fp
