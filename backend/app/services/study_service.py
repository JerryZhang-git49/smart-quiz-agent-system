import asyncio

import structlog
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.config import get_settings
from app.llm.langchain_factory import get_chat_model
from app.models.study import (
    StudyAdviceResponse,
    StudyClockReading,
)
from app.prompts.study_prompt import STUDY_AGENT_SYSTEM_PROMPT
from app.tools.learning_tools import build_time_tool


logger = structlog.getlogger()

def _build_agent(time_tool):
    return create_react_agent(
        get_chat_model(temperature=0.1),
        tools=[time_tool],
        prompt=STUDY_AGENT_SYSTEM_PROMPT,
    )


async def handle_study_advice(
        user_input: str,
) -> StudyAdviceResponse:
    settings = get_settings()

    readings : list[StudyClockReading] = []
    tool = build_time_tool(
        timezone_name = settings.study_timezone,
        onresult = readings.append,
    )

    try:
        agent = _build_agent(tool)
        result = await asyncio.wait_for(
            agent.ainvoke(
                {
                    "messages":[
                        {
                            "role": "user",
                            "content": user_input,
                        }
                    ]
                },
                config = {"recursion_limit": 8},
            ),
            timeout = settings.study_agent_timeout_seconds
        )

        messages = result.get("messages", [])
        for message in messages:
            for call in getattr(message, "tool_calls", []) or []:
                logger.info(
                    "study_agent_tool_call",
                    tool_name = call.get("name"),
                )

        final_message = message[-1] if messages else None

        if(
            not isinstance(final_message, AIMessage)
            or final_message.tool_calls
            or not isinstance(final_message.content, str)
            or not final_message.content.strip()
        ):
            raise ValueError("Agent 没有返回完整的文本")


        return StudyAdviceResponse(
            advice = final_message.content.strip(),
            clock = readings[-1] if readings else None,
            use_tools = (
                ["get_current_time_and_tip"] if readings else []
            )
        )

    except Exception as exc:
        logger.warning(
            "study_advice_fallback",
            error_type=type(exc).__name__,
        )

        # 即使模型最后超时，已经成功读取的时间仍然可以使用
        clock = readings[-1] if readings else None

