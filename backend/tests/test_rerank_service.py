"""使用 HTTP MockTransport 验证百炼协议、超时和异常响应。"""

import asyncio
import json

import httpx
import pytest
from langchain_core.documents import Document

from app.core.config import Settings
from app.services import rerank_service


@pytest.fixture
def settings(monkeypatch):
    configured = Settings(
        _env_file=None, rerank_api_key="test-key", rerank_timeout_seconds=0.05,
    )
    monkeypatch.setattr(rerank_service, "get_settings", lambda: configured)
    return configured


def use_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        rerank_service.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.asyncio
async def test_native_api_payload_and_descending_scores(settings, monkeypatch):
    def handler(request):
        assert str(request.url) == settings.rerank_api_url
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "gte-rerank",
            "input": {"query": "异常处理", "documents": ["候选一", "候选二", "候选三"]},
            "parameters": {"top_n": 2, "return_documents": False},
        }
        return httpx.Response(200, json={"output": {"results": [
            {"index": 0, "relevance_score": 0.2}, {"index": 2, "relevance_score": 0.9},
        ]}})
    use_transport(monkeypatch, handler)
    hits = await rerank_service.rerank(
        "异常处理", [Document(page_content=f"候选{x}") for x in "一二三"], 2,
    )
    assert [hit.index for hit in hits] == [2, 0]


@pytest.mark.parametrize("results", [
    [],
    [{"index": 0, "relevance_score": 0.5}],  # 少于 top_n。
    [{"index": 0, "relevance_score": 0.5}, {"index": 0, "relevance_score": 0.4}],
    [{"index": 0, "relevance_score": 0.5}, {"index": 2, "relevance_score": 0.4}],
    [{"index": -1, "relevance_score": 0.5}, {"index": 0, "relevance_score": 0.4}],
    [{"index": "1", "relevance_score": 0.5}, {"index": 0, "relevance_score": 0.4}],
    [{"index": True, "relevance_score": 0.5}, {"index": 0, "relevance_score": 0.4}],
    [{"index": 1, "relevance_score": "NaN"}, {"index": 0, "relevance_score": 0.4}],
    [{"index": 1, "relevance_score": "Infinity"}, {"index": 0, "relevance_score": 0.4}],
])
@pytest.mark.asyncio
async def test_invalid_provider_results_raise(settings, monkeypatch, results):
    use_transport(monkeypatch, lambda request: httpx.Response(200, json={"output": {"results": results}}))
    with pytest.raises(ValueError):
        await rerank_service.rerank("query", [Document(page_content="a"), Document(page_content="b")], 2)


@pytest.mark.asyncio
async def test_total_timeout_cancels_request(settings, monkeypatch):
    cancelled = asyncio.Event()
    async def handler(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
        return httpx.Response(200)
    use_transport(monkeypatch, handler)
    with pytest.raises(asyncio.TimeoutError):
        await rerank_service.rerank("query", [Document(page_content="a")], 1)
    assert cancelled.is_set()


@pytest.mark.parametrize("status", [401, 429, 500])
@pytest.mark.asyncio
async def test_http_errors_propagate_to_retrieval_fallback(settings, monkeypatch, status):
    use_transport(monkeypatch, lambda request: httpx.Response(status, json={"code": "provider-error"}))
    with pytest.raises(httpx.HTTPStatusError):
        await rerank_service.rerank("query", [Document(page_content="a")], 1)


@pytest.mark.asyncio
async def test_invalid_json_raises(settings, monkeypatch):
    use_transport(monkeypatch, lambda request: httpx.Response(200, text="invalid json"))
    with pytest.raises(ValueError):
        await rerank_service.rerank("query", [Document(page_content="a")], 1)


@pytest.mark.asyncio
async def test_key_falls_back_to_embedding_key(settings, monkeypatch):
    settings.rerank_api_key = " "
    settings.dashscope_api_key = "shared-test-key"
    def handler(request):
        assert request.headers["Authorization"] == "Bearer shared-test-key"
        return httpx.Response(200, json={"output": {"results": [{"index": 0, "relevance_score": 1}]}})
    use_transport(monkeypatch, handler)
    assert len(await rerank_service.rerank("query", [Document(page_content="a")], 3)) == 1


@pytest.mark.asyncio
async def test_no_key_fails_before_network(settings):
    settings.rerank_api_key = settings.dashscope_api_key = ""
    with pytest.raises(ValueError, match="API Key"):
        await rerank_service.rerank("query", [Document(page_content="a")], 1)
