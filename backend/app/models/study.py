"""学习建议请求和响应模型。"""
from pydantic import BaseModel, Field,field_validator

class StudyAdviceRequest(BaseModel):
    """学习建议请求"""
    user_input : str = Field(min_length=1, max_length=500)

    @field_validator('user_input')
    @classmethod
    def validate_user_input(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("学习要求不能为空")
        return value


class StudyClockReading(BaseModel):
    """给 @tool 工具用（要求工具必须返回严格的时区、建议学习时长、休息时长）"""
    # ISO 格式，包含时区偏移，例如：
    # 2026-11-14T21:40+08:00
    current_time: str
    timezone : str

    suggested_study_minutes : int = Field(gt=0)
    suggested_break_minutes : int = Field(gt=0)
    tip : str


class StudyAdviceResponse(BaseModel):
    """学习建议响应"""
    advice : str
    # 时间数据直接来自工具
    clock : StudyClockReading | None = None
    # 记录本次成功获得结果的工具，便于后续分析和优化
    used_tools : list[str] = Field(default_factory=list)

    # 模型异常或超时时，是否返回降级建议
    degraded : bool = False