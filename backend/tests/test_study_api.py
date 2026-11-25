"""学习建议路由与请求校验。"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.routes import study
from app.main import app
from app.models.study import StudyAdviceResponse


@pytest.mark.asyncio
async def test_advice_route_returns_observable_fallback(monkeypatch):
    service = AsyncMock(return_value=StudyAdviceResponse(advice="先复习一个知识点。", degraded=True))
    monkeypatch.setattr(study, "handle_study_advice", service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/study/advice", json={"user_input": "  复习 Python  "})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "advice": "先复习一个知识点。", "clock": None, "used_tools": [], "degraded": True,
    }
    service.assert_awaited_once_with("复习 Python")


@pytest.mark.parametrize("value", ["", "   ", "x" * 501, None])
@pytest.mark.asyncio
async def test_invalid_input_never_calls_agent(monkeypatch, value):
    service = AsyncMock()
    monkeypatch.setattr(study, "handle_study_advice", service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/study/advice", json={"user_input": value})
    assert response.status_code == 422
    service.assert_not_called()


@pytest.mark.asyncio
async def test_filtered_input_never_calls_agent(monkeypatch):
    service = AsyncMock()
    monkeypatch.setattr(study, "handle_study_advice", service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/study/advice", json={"user_input": "赌博"})
    assert response.status_code == 400
    service.assert_not_called()
