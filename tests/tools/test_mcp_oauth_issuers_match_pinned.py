"""Fork nail (20261108 merge, SDK增量对照): upstream 1dadda835d calls
``from mcp.client.auth.utils import issuers_match`` inside the PRM metadata shim
(tools/mcp_oauth_provider.py), but the pinned mcp 2.0.0 predates that export —
bare, every OAuth metadata discovery response dies with ImportError before the
handshake. The fork carries a verbatim-rule fallback at module scope; this nail
pins BOTH that the symbol is importable on the pin and the exact RFC 8414 §3.3
rule (root trailing slash only — NOT a blanket rstrip, which would also equate
path-bearing issuers the SDK keeps distinct). Re-activates as a no-op when the
env SDK upgrades and supplies the real function.
"""
import pytest

pytest.importorskip("mcp.client.auth.oauth2")  # same gate as upstream's issuer-origin tests

from tools.mcp_oauth_provider import issuers_match  # noqa: E402


@pytest.mark.parametrize("a,b,expected", [
    # exact match
    ("https://as.example", "https://as.example", True),
    # root issuer with/without trailing slash — the Otter.ai #132233 case
    ("https://otter.ai", "https://otter.ai/", True),
    ("https://otter.ai/", "https://otter.ai", True),
    # anti-rstrip: a path-bearing issuer keeps its trailing slash distinct — blanket rstrip would
    # wrongly equate this pair (the ONLY rstrip flip among the 8; 20261108 review correction: the
    # earlier "two anti-rstrip cases" claim was wrong)
    ("https://as.example/mcp-issuer", "https://as.example/mcp-issuer/", False),
    # anti-root-folding: a bare root is NOT its path-bearing child — rstrip already keeps these
    # distinct; this case defeats origin-equality simplifications (scheme://netloc prefix matching)
    ("https://www.strava.com", "https://www.strava.com/mcp-issuer", False),
    # different authorities never match
    ("https://as.example", "https://other.example", False),
    # scheme/host case and default ports are NOT normalized (plain string rule)
    ("https://AS.example", "https://as.example", False),
    ("https://as.example:443", "https://as.example", False),
])
def test_issuers_match_rule(a, b, expected):
    assert issuers_match(a, b) is expected


def test_fallback_importable_on_pinned_sdk():
    """On the pinned mcp 2.0.0 this attribute only exists because of the fork fallback —
    deleting the except-branch (or the verbatim rule) makes the import above fail."""
    assert callable(issuers_match)
