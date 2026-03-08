from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import AnalyzeRequest, RecommendRequest, RecommendResponse, VisionAnalysisResult
from app.services.recommend_service import RecommendService
from app.services.vision_service import VisionService

router = APIRouter(prefix="/api", tags=["ai"])
vision_service = VisionService()
recommend_service = RecommendService()


@router.post("/analyze", response_model=VisionAnalysisResult)
async def analyze_image(payload: AnalyzeRequest) -> VisionAnalysisResult:
    return await vision_service.analyze(payload)


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_outfit(payload: RecommendRequest) -> RecommendResponse:
    return recommend_service.recommend(
        items=payload.items,
        occasion=payload.occasion or "casual",
        temperature_c=payload.temperature_c,
    )
