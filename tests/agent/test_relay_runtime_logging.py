"""Regression tests: the optional ``nemo_relay`` binding must be reported once per process
instead of replaying an import traceback on every event (live: ~110 log storms/month)."""

import importlib
import logging

import pytest

from agent import relay_runtime
from agent.relay_runtime import RelayHostRegistry, _load_nemo_relay


@pytest.fixture(autouse=True)
def _reset_relay_state(monkeypatch):
    monkeypatch.setattr(relay_runtime, "_NEMO_RELAY_IMPORT_ERROR", None)
    relay_runtime.HOST_REGISTRY._hosts.clear()


def test_missing_binding_warns_once_then_reraises_cached(caplog, monkeypatch):
    def _boom(name, *args, **kwargs):
        raise ModuleNotFoundError(f"No module named '{name}'")

    monkeypatch.setattr(importlib, "import_module", _boom)

    with caplog.at_level(logging.DEBUG, logger="agent.relay_runtime"):
        with pytest.raises(ModuleNotFoundError):
            _load_nemo_relay()
        with pytest.raises(ModuleNotFoundError):
            _load_nemo_relay()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "nemo_relay" in warnings[0].getMessage()
    assert not warnings[0].exc_info, "root-cause warning must not carry a traceback"


def test_missing_binding_falls_back_to_noop_with_debug_only(caplog, monkeypatch):
    """End to end through a real RelayRuntime init: the missing binding yields one plain
    WARNING (root cause, no traceback) and per-key DEBUG fallbacks — never per-key WARNINGs."""

    def _boom(name, *args, **kwargs):
        raise ModuleNotFoundError(f"No module named '{name}'")

    monkeypatch.setattr(importlib, "import_module", _boom)
    registry = RelayHostRegistry()

    with caplog.at_level(logging.DEBUG, logger="agent.relay_runtime"):
        host1 = registry.for_profile("profile-a")
        host2 = registry.for_profile("profile-a")
        host3 = registry.for_profile("profile-b")

    assert host1 is not None and host1 is host2  # Noop fallback cached per key
    assert type(host1).__name__ == "NoopRelayRuntime"
    assert host3 is not None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "nemo_relay" in warnings[0].getMessage() and not warnings[0].exc_info
    fallback_debugs = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "optional binding missing" in r.getMessage()
    ]
    assert len(fallback_debugs) == 2  # profile-a once + profile-b once


def test_unexpected_init_failure_still_warns_with_traceback(monkeypatch, caplog):
    """Non-import init failures are not noise: they keep the loud WARNING path."""

    def _broken_init(*args, **kwargs):
        raise RuntimeError("simulated config failure")

    monkeypatch.setattr(relay_runtime, "RelayRuntime", _broken_init)
    registry = RelayHostRegistry()

    with caplog.at_level(logging.DEBUG, logger="agent.relay_runtime"):
        host = registry.for_profile("profile-a")

    assert host is not None and type(host).__name__ == "NoopRelayRuntime"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and warnings[0].exc_info
