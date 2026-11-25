"""学习建议路由"""
from fastapi import APIRouter

from app.core.exceptions import ContentFilterError
from app.core.security import check_content
from app.models.common import ApiResponse
from app.models.study import StudyAdviceRequest
from app.services.study_service import handle_study_advice

router = APIRouter(prefix="/study", tags=["study"])

@router.post("/advice", response_model=ApiResponse)
async def study_advice(req: StudyAdviceRequest):
    if not check_content(req.user_input):
        raise ContentFilterError()
    result = await handle_study_advice(req.user_input)
    return ApiResponse.success(data=result.model_dump())
