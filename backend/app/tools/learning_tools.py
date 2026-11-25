"""学习相关的自定义 Agent 工具。"""

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from langchain_core.tools import BaseTool, tool

from app.models.study import StudyClockReading


logger = structlog.get_logger()

def build_clock_reading(
        now: datetime,
        timezone_name: str,
) -> StudyClockReading:
    """根据指定时间生成建议，也方便测试时传入固定时间。"""
    if now.tzinfo is None:
        # 检查时区信息，判断是否为空
        raise ValueError("必须传入带时区的时间")
    # 将时间转换为指定时区
    local_time = now.astimezone(ZoneInfo(timezone_name))
    hour = local_time.hour
    if hour < 6 or hour >= 22:
        study_minutes = 10
        break_minutes = 5
        tip = "时间较晚，适合简短复习，优先保证休息。"
    elif 12 <= hour < 14:
        study_minutes = 15
        break_minutes = 5
        tip = "午间适合轻量复习，完成一个小目标即可。"
    else:
        study_minutes = 25
        break_minutes = 5
        tip = "可以安排一轮专注学习，结束后短暂休息。"

    return StudyClockReading(
        current_time=local_time.isoformat(timespec='minutes'),
        timezone=timezone_name,
        suggested_study_minutes=study_minutes,
        suggested_break_minutes=break_minutes,  
        tip=tip
    )


def read_clock(timezone_name:str)-> StudyClockReading:
    now = datetime.now(ZoneInfo(timezone_name))
    return build_clock_reading(now, timezone_name)


def build_time_tool(
        timezone_name: str,
        on_result: Callable[[StudyClockReading], None],   # 在工具内部获取到精准的 StudyClockReading 对象后，通过回调函数将真实的物理数据直接穿透（Bypass）给后端业务层，存入最终返回给前端的 clock 字段
    ) -> BaseTool:
    """
    为一次请求构建时间工具。

    timezone_name 由后端配置决定，不由模型随意传入。
    on_result 保存工具的真实结果，供接口直接返回。
    """
    @tool
    async def get_current_time_and_tip() -> dict:
        """查询配置时区的真实当前时间，并提供基础学习时长和休息建议。

        用户询问现在几点、当前日期，或需要结合当前时段安排学习时使用。
        不需要输入参数。
        """
        logger.info("get_current_time 工具被调用")

        try:
            reading = read_clock(timezone_name)
            on_result(reading)
            return {
                "ok": True,
                **reading.model_dump(),
            }
        except Exception as exc:
            logger.warning(
                "study_clock_tool_failed",
                error_type=type(exc).__name__,
            )
            return {
                "ok": False,
                "message": (
                    "当前时间暂时不可用。"
                    "请提供不依赖当前时间的通用学习建议。"
                ),
            }

    return get_current_time_and_tip
