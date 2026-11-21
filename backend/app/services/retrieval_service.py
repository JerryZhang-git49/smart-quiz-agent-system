"""知识库两阶段检索编排"""

import asyncio
import time

import structlog
from langchain_core.documents import Document

from app.core.config import get_settings

from app.service import(
    rerank_service,
    vector_store_service,
)

logger = structlog.get_logger()

async def retrieve_documents(
        user_id: int,
        doc_id: str,
        query: str,
) -> list[Document]:
    query = query.strip()

    if not query:
        return []

    settings = get_settings()

    # rerank开关关闭时保持原有向量检索行为
    if not settings.enable_rerank:
        return await asyncio.to_thread(
            vector_store_service.similarity_search,
            user_id=user_id,
            doc_id=doc_id,
            query=query,
            k=settings.kb_retrieve_top_k
        )
    final_k = settings.kb_rerank_top_k
    # 防止召回数量小于最终需要的向量数量
    recall_k = max(settings.kb_recall_k, final_k)

    # 第一阶段： Chroma向量召回
    candidates = await asyncio.to_thread(
        vector_store_service.similarity_search,
        user_id=user_id,
        doc_id=doc_id,
        query=query,
        k=recall_k,
    )

    if not candidates:
        return []

    # 保留原向量顺序，重排失败时直接使用，不重复检索
    fallback_documents = candidates[:final_k]
    started_at = time.monotonic()

    try:
        # 第二阶段：相关性重排
        hits = await rerank_service.rerank(
            query=query,
            documents=candidates,
            top_k=final_k,
        )

        if not hits:
            raise ValueError("重排结果未空")

        # 按索引返回原始Documents。保留全部元数据
        selected_documents = [
            candidates[hit.index] for hit in hits
        ]

        logger.info(
            "kb_rerank_completed",
            recalled=len(candidates),
            selected=len(selected_documents),
            selected_indices=[hit.index for hit in hits],
            elapsed_ms=round(
                (time.monotonic() - started_at) * 1000
            ),
        )

        return selected_documents

    except Exception as exc:
        logger.warning(
            "kb_rerank_fallback",
            error_type=type(exc).__name__,
            recalled=len(candidates),
            selected=len(fallback_documents),
            elapsed_ms=round(
                (time.monotonic() - started_at) * 1000
            ),
        )

        return fallback_documents