"""学习工具、Agent 消息与部分成功降级的回归测试，不调用外部 API。"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.core.config import Settings
from app.services import study_service
from app.tools import learning_tools


@pytest.fixture
def settings(monkeypatch):
    configured = Settings(_env_file=None, study_advice_timeout_seconds=0.03)
    monkeypatch.setattr(study_service, "get_settings", lambda: configured)
    return configured


@pytest.mark.parametrize("hour,minutes", [(1, 10), (12, 15), (16, 25), (22, 10)])
def test_clock_uses_configured_timezone(hour, minutes):
    reading = learning_tools.build_clock_reading(
        datetime(2026, 11, 25, hour, tzinfo=timezone.utc), "UTC"
    )
    assert reading.current_time.endswith("+00:00")
    assert reading.suggested_study_minutes == minutes
    assert reading.suggested_break_minutes == 5


def test_clock_converts_timezone_and_rejects_naive_time():
    reading = learning_tools.build_clock_reading(
        datetime(2026, 11, 25, 15, tzinfo=timezone.utc), "Asia/Shanghai"
    )
    assert reading.current_time == "2026-11-25T23:00+08:00"
    assert reading.suggested_study_minutes == 10
    with pytest.raises(ValueError):
        learning_tools.build_clock_reading(datetime(2026, 11, 25), "UTC")


@pytest.mark.asyncio
async def test_tool_captures_real_data_outside_model():
    readings = []
    tool = learning_tools.build_time_tool("UTC", readings.append)
    assert tool.args == {}  # 时区和回调不暴露给模型。
    result = await tool.ainvoke({})
    assert result["ok"] is True
    assert result["current_time"] == readings[0].current_time
    assert readings[0].timezone == "UTC"


@pytest.mark.asyncio
async def test_bad_timezone_returns_failure_without_recording_time():
    readings = []
    tool = learning_tools.build_time_tool("Invalid/Timezone", readings.append)
    result = await tool.ainvoke({})
    assert result["ok"] is False
    assert readings == []


class ToolCallingFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@pytest.mark.asyncio
async def test_actual_react_graph_calls_tool_and_returns_trusted_clock(settings, monkeypatch):
    settings.study_advice_timeout_seconds = 5
    fake_model = ToolCallingFakeModel(responses=[
        AIMessage(content="", tool_calls=[
            {"name": "get_current_time_and_tip", "args": {}, "id": "clock-1"}
        ]),
        AIMessage(content="先复习三个 Python 知识点，再做练习。"),
    ])
    monkeypatch.setattr(study_service, "get_chat_model", lambda **kwargs: fake_model)
    result = await study_service.handle_study_advice("现在几点了？我想复习 Python")
    assert result.clock is not None
    assert result.used_tools == ["get_current_time_and_tip"]
    assert not result.degraded
    assert "Python" in result.advice


@pytest.mark.asyncio
async def test_plain_advice_can_return_without_time(settings, monkeypatch):
    agent = AsyncMock()
    agent.ainvoke.return_value = {"messages": [AIMessage(content="复习列表推导式。") ]}
    monkeypatch.setattr(study_service, "_build_agent", lambda tool: agent)
    result = await study_service.handle_study_advice("列表怎么复习？")
    assert result.advice == "复习列表推导式。"
    assert result.clock is None
    assert result.used_tools == []
    assert not result.degraded


@pytest.mark.asyncio
async def test_timeout_keeps_successful_tool_result(settings, monkeypatch):
    cancelled = asyncio.Event()

    def build_agent(tool):
        async def invoke(*args, **kwargs):
            await tool.ainvoke({})
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        return AsyncMock(ainvoke=AsyncMock(side_effect=invoke))

    monkeypatch.setattr(study_service, "_build_agent", build_agent)
    result = await study_service.handle_study_advice("现在适合学多久？")
    assert cancelled.is_set()
    assert result.degraded
    assert result.clock is not None
    assert result.used_tools == ["get_current_time_and_tip"]
    assert str(result.clock.suggested_study_minutes) in result.advice


@pytest.mark.asyncio
async def test_build_failure_returns_generic_fallback(settings, monkeypatch):
    def fail(tool):
        raise RuntimeError("private-provider-error")
    monkeypatch.setattr(study_service, "_build_agent", fail)
    result = await study_service.handle_study_advice("复习 Python")
    assert result.degraded
    assert result.clock is None
    assert result.used_tools == []
    assert "private-provider-error" not in result.advice


@pytest.mark.parametrize("messages", [
    [], [HumanMessage(content="问题")], [AIMessage(content=" ")],
    [AIMessage(content="", tool_calls=[{"name": "get_current_time_and_tip", "args": {}, "id": "a"}])],
])
@pytest.mark.asyncio
async def test_invalid_final_message_degrades(settings, monkeypatch, messages):
    agent = AsyncMock()
    agent.ainvoke.return_value = {"messages": messages}
    monkeypatch.setattr(study_service, "_build_agent", lambda tool: agent)
    result = await study_service.handle_study_advice("学习建议")
    assert result.degraded
    assert result.advice


@pytest.mark.asyncio
async def test_failed_time_tool_marks_degraded(settings, monkeypatch):
    agent = AsyncMock()
    agent.ainvoke.return_value = {"messages": [
        AIMessage(content="", tool_calls=[{"name": "get_current_time_and_tip", "args": {}, "id": "a"}]),
        AIMessage(content="暂时无法确认时间，可以先复习一个小知识点。"),
    ]}
    monkeypatch.setattr(study_service, "_build_agent", lambda tool: agent)
    result = await study_service.handle_study_advice("现在几点了？")
    assert result.degraded
    assert result.clock is None
    assert result.used_tools == []
