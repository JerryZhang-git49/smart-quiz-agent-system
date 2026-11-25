"""两阶段检索、用户文档隔离参数及回退行为。"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.documents import Document

from app.core.config import Settings
from app.services import retrieval_service
from app.services.rerank_service import RankedHit


@pytest.fixture
def setup(monkeypatch):
    settings = Settings(_env_file=None, enable_rerank=True)
    documents = [Document(page_content=f"内容 {i}", metadata={"page": i, "doc_id": "doc_7"}) for i in range(20)]
    search = Mock(return_value=documents)
    rerank = AsyncMock(return_value=[
        RankedHit(index=i, relevance_score=1 - j / 10) for j, i in enumerate([7, 2, 14])
    ])
    monkeypatch.setattr(retrieval_service, "get_settings", lambda: settings)
    monkeypatch.setattr(retrieval_service.vector_store_service, "similarity_search", search)
    monkeypatch.setattr(retrieval_service.rerank_service, "rerank", rerank)
    return settings, documents, search, rerank


@pytest.mark.asyncio
async def test_top20_to_top3_preserves_document_objects(setup):
    settings, documents, search, rerank = setup
    selected = await retrieval_service.retrieve_documents(12, "doc_7", "  Python 异常处理  ")
    search.assert_called_once_with(user_id=12, doc_id="doc_7", query="Python 异常处理", k=20)
    rerank.assert_awaited_once_with(query="Python 异常处理", documents=documents, top_k=3)
    assert [item.metadata["page"] for item in selected] == [7, 2, 14]
    assert selected[0] is documents[7]


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), RuntimeError("provider unavailable"), ValueError("invalid results")])
@pytest.mark.asyncio
async def test_rerank_error_returns_original_top3_without_second_search(setup, error):
    settings, documents, search, rerank = setup
    rerank.side_effect = error
    selected = await retrieval_service.retrieve_documents(12, "doc_7", "Python")
    assert selected == documents[:3]
    search.assert_called_once()


@pytest.mark.asyncio
async def test_empty_rerank_result_falls_back(setup):
    settings, documents, search, rerank = setup
    rerank.return_value = []
    assert await retrieval_service.retrieve_documents(12, "doc_7", "Python") == documents[:3]


@pytest.mark.asyncio
async def test_disabled_keeps_original_top4(setup):
    settings, documents, search, rerank = setup
    settings.enable_rerank = False
    search.return_value = documents[:4]
    assert await retrieval_service.retrieve_documents(12, "doc_7", "Python") == documents[:4]
    assert search.call_args.kwargs["k"] == 4
    rerank.assert_not_called()


@pytest.mark.asyncio
async def test_no_candidates_does_not_call_rerank(setup):
    settings, documents, search, rerank = setup
    search.return_value = []
    assert await retrieval_service.retrieve_documents(12, "doc_7", "Python") == []
    rerank.assert_not_called()


@pytest.mark.asyncio
async def test_blank_query_does_not_call_services(setup):
    settings, documents, search, rerank = setup
    assert await retrieval_service.retrieve_documents(12, "doc_7", "   ") == []
    search.assert_not_called()
    rerank.assert_not_called()


@pytest.mark.asyncio
async def test_recall_never_smaller_than_final_count(setup):
    settings, documents, search, rerank = setup
    settings.kb_recall_k = 1
    await retrieval_service.retrieve_documents(12, "doc_7", "Python")
    assert search.call_args.kwargs["k"] == 3


@pytest.mark.asyncio
async def test_request_cancellation_is_not_swallowed_as_fallback(setup):
    settings, documents, search, rerank = setup
    rerank.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await retrieval_service.retrieve_documents(12, "doc_7", "Python")
