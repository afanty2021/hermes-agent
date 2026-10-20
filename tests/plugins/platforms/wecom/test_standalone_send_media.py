"""WeCom ``_standalone_send`` media delivery.

``hermes send --to wecom:... "text MEDIA:file"`` runs in a process without the
gateway's adapters, so the send routes to the plugin's standalone sender. That
sender used to accept ``media_files`` and silently drop them — the text arrived,
the file never did, and the routing layer returns before its dropped-media
warning, so the caller saw a plain success. The standalone sender must deliver
media through the adapter's native media APIs on the same (live or ephemeral)
WebSocket it already uses for text.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.platforms.base import SendResult
from plugins.platforms.wecom.adapter import _standalone_send


class _FakeAdapter:
    """Just enough of WeComAdapter for the media path: a text send plus a native
    ``send_document``. The methods live on the CLASS (delegating to per-instance
    mocks) because _send_live_adapter_media's capability check resolves against
    ``type(adapter)``, mirroring how the real mixin provides them."""

    def __init__(self):
        self.send_mock = AsyncMock(return_value=SendResult(success=True, message_id="t1"))
        self.document_mock = AsyncMock(return_value=SendResult(success=True, message_id="m1"))

    async def send(self, chat_id=None, content=None, **kwargs):
        return await self.send_mock(chat_id=chat_id, content=content, **kwargs)

    async def send_document(self, chat_id, file_path, caption=None, file_name=None,
                            reply_to=None, **kwargs):
        return await self.document_mock(chat_id, file_path, caption=caption, reply_to=reply_to, **kwargs)

    async def connect(self):
        return True

    async def disconnect(self):
        pass


@pytest.fixture
def pdf(tmp_path):
    f = tmp_path / "report.pdf"
    f.write_bytes(b"%PDF-1.4 minimal")
    return str(f)


async def _patched_live_adapter(monkeypatch, adapter):
    import tools.send_message_senders as senders

    def _fake(platform):  # _live_adapter is sync: returns (runner, adapter)
        return SimpleNamespace(), adapter

    monkeypatch.setattr(senders, "_live_adapter", _fake)


class TestStandaloneSendMedia:
    @pytest.mark.asyncio
    async def test_media_rides_the_live_adapter_document_api(self, monkeypatch, pdf):
        adapter = _FakeAdapter()
        await _patched_live_adapter(monkeypatch, adapter)

        result = await _standalone_send(
            None, "HuangZhengBo", "here is the file", media_files=[(pdf, False)])

        assert result.get("success") is True
        assert result.get("media_delivered") is True
        adapter.document_mock.assert_awaited_once()
        args, kwargs = adapter.document_mock.await_args
        assert args[0] == "HuangZhengBo" and args[1] == pdf
        assert kwargs.get("caption") == "here is the file"

    @pytest.mark.asyncio
    async def test_media_rides_an_ephemeral_adapter(self, monkeypatch, pdf):
        """No live adapter (CLI process): an ephemeral WeComAdapter connects, delivers the
        file through the same media API, and disconnects afterwards."""
        import plugins.platforms.wecom.adapter as adapter_mod
        import tools.send_message_senders as senders

        def _none(platform):  # sync: no live adapter in a CLI process
            return SimpleNamespace(), None

        monkeypatch.setattr(senders, "_live_adapter", _none)
        monkeypatch.setattr(adapter_mod, "check_wecom_requirements", lambda: True)
        fake = _FakeAdapter()
        fake.disconnect = AsyncMock()
        monkeypatch.setattr(adapter_mod, "WeComAdapter", lambda pconfig: fake)

        result = await _standalone_send(
            object(), "HuangZhengBo", "caption", media_files=[(pdf, False)], force_document=True)

        assert result.get("success") is True and result.get("media_delivered") is True
        fake.document_mock.assert_awaited_once_with(
            "HuangZhengBo", pdf, caption="caption", reply_to=None, metadata=None)
        fake.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_text_only_keeps_the_plain_send_path(self, monkeypatch):
        adapter = _FakeAdapter()
        await _patched_live_adapter(monkeypatch, adapter)

        result = await _standalone_send(None, "HuangZhengBo", "just text")

        assert result.get("success") is True
        assert "media_delivered" not in result
        adapter.send_mock.assert_awaited_once()
        adapter.document_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_media_failure_reports_error_not_success(self, monkeypatch, pdf):
        """A rejected upload must surface as an error dict — the old code reported plain
        success for media sends, hiding the dropped file."""
        adapter = _FakeAdapter()
        adapter.document_mock = AsyncMock(
            return_value=SendResult(success=False, error="media too large"))
        await _patched_live_adapter(monkeypatch, adapter)

        result = await _standalone_send(None, "HuangZhengBo", "c", media_files=[(pdf, False)])

        assert result.get("success") is None
        assert "media too large" in result.get("error", "")
