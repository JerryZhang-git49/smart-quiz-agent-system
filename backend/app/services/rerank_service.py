"""百炼 Rerank 接口适配层"""

import asyncio

import httpx
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from app.core.config import get_settings

class RankedHit(BaseModel):
    # 必须是合法整数， 不接受字符串索引
    index: int = Field(ge=0, strict=True)

    # 不接受NAN、Infinity等异常分数
    relevance_score: float = Field(allow_inf_nan=False)

class RerankOutput(BaseModel):
    results: list[RankedHit]

class RerankResponse(BaseModel):
    output: RerankOutput


async def rerank(
        query: str,
        documents: list[Document],
        top_k: int,
) -> list[RankedHit]:
    if not documents:
        return []

    if not query.strip():
        raise ValueError("重排 query 不能为空")

    if top_k < 1:
        raise ValueError("top_k必须大于0")

    settings = get_settings()

    api_key = settings.rerank_api_key.strip() or settings.dashscope_api_key.strip()

    if not api_key:
        raise ValueError("未配置 Rerank API Key")

    limit = min(top_k, len(documents))
    timeout_seconds = settings.rerank_timeout_seconds

    payload = {
        "model": settings.rerank_model,
        "input":{
            "query": query,
            "documents": [
                document.page_content for document in documents
            ],
        },
        "parameters":{
            "top_n": limit,
            "return_documents": False,
        },
    }

    # wait_for 限制整个 HTTP 调用的预算，同时兼容 Python 3.10。
    async def request_rerank() -> RerankResponse:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(1.0, timeout_seconds),
            )
        ) as client:
            response = await client.post(
                settings.rerank_api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            response.raise_for_status()

            return RerankResponse.model_validate(response.json())

    parsed = await asyncio.wait_for(request_rerank(), timeout=timeout_seconds)

    hits = parsed.output.results

    if len(hits) < limit:
        raise ValueError("Rerank 返回结果不足")

    seen_indices: set[int] = set()

    for hit in hits:
        if hit.index >= len(documents):
            raise ValueError("Rerank 返回了越界索引")
        if hit.index in seen_indices:
            raise ValueError("Rerank返回了重复索引")

        seen_indices.add(hit.index)

    return sorted(
        hits,
        key = lambda hit: hit.relevance_score,
        reverse=True,
    )[:limit]
