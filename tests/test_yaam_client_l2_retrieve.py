import os
import sys

import httpx
import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


def test_retrieve_l2_facts_returns_list() -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/memory/l2/facts"
        return httpx.Response(status_code=200, request=request, json=[{"fact": "x"}])

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    out = client.retrieve_l2_facts(session_id="s", agent_id="a", task_id="t", traceparent="tp")
    assert out == [{"fact": "x"}]


def test_retrieve_l2_facts_dict_results_is_unwrapped() -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, request=request, json={"results": [{"k": 1}]})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    out = client.retrieve_l2_facts(session_id="s", agent_id="a", task_id="t", traceparent="tp")
    assert out == [{"k": 1}]


@pytest.mark.parametrize("status_code", [501, 502])
def test_retrieve_l2_facts_swallow_501_502(
    status_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, request=request, json={"error": "backend unavailable"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    out = client.retrieve_l2_facts(session_id="s", agent_id="a", task_id="t", traceparent="tp")
    assert out == []

    captured = capsys.readouterr()
    assert f"YAAM {status_code}" in captured.err

