import json
import threading
import time
import urllib.request
import pytest

from src.api import APIServerHandler
from http.server import ThreadingHTTPServer


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), APIServerHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _post(base_url, path, payload):
    req = urllib.request.Request(
        f"{base_url}{path}", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(base_url, path):
    with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_manual_levels_crud_roundtrip(server):
    empty = _get(server, "/api/options/levels/manual?ticker=ZZZZ")
    assert empty == []
    added = _post(server, "/api/options/levels/manual", {"ticker": "ZZZZ", "price": 123.45, "label": "test level"})
    assert {"price": 123.45, "label": "test level"} in added
    deleted = _post(server, "/api/options/levels/manual/delete", {"ticker": "ZZZZ", "price": 123.45})
    assert deleted == []


def test_full_audit_endpoint_returns_expected_shape(server):
    result = _post(server, "/api/options/full_audit", {"ticker": "AAPL"})
    assert result["success"] is True
    assert result["ticker"] == "AAPL"
    assert "levels" in result
    assert "levels_below" in result["levels"]
    assert "buckets" in result
    assert "top_pick" in result
    assert "gate_result" in result["top_pick"]
    assert result["top_pick"]["gate_result"]["overall"] in ("AUDIT PASSED", "AUDIT FAILED")


def test_full_audit_gate_endpoint(server):
    contract = {"strike": 200.0, "bid": 1.0, "ask": 1.1, "midpoint": 1.05, "open_interest": 1000,
                "greeks": {"delta": 0.45}, "symbol": "AAPL260815C00200000"}
    result = _post(server, "/api/options/full_audit/gate", {
        "ticker": "AAPL", "expiration": "2026-08-15", "strategy": "LONG CALL",
        "selected_contract": contract, "iv_rank": 30.0, "dte": 23,
    })
    assert result["success"] is True
    assert result["gate_result"]["overall"] in ("AUDIT PASSED", "AUDIT FAILED")
