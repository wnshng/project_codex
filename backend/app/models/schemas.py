from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


Category = Literal[
    "top",
    "bottom",
    "outer",
    "dress",
    "shoes",
    "bag",
    "accessory",
    "unknown",
]


class AnalyzeRequest(BaseModel):
    image_url: Optional[HttpUrl] = None
    image_base64: Optional[str] = None


class VisionAnalysisResult(BaseModel):
    category: Category = "unknown"
    colors_hex: List[str] = Field(default_factory=list)
    material: Optional[str] = None
    pattern: Optional[str] = None
    formality: Optional[Literal["casual", "smart-casual", "formal"]] = None
    style_tags: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class ClothingItem(BaseModel):
    item_id: str
    category: Category
    color_hex: str
    style_tags: List[str] = Field(default_factory=list)
    season: List[Literal["spring", "summer", "fall", "winter"]] = Field(default_factory=list)
    warmth_level: int = Field(default=3, ge=1, le=5)


class RecommendRequest(BaseModel):
    items: List[ClothingItem]
    occasion: Optional[str] = "casual"
    temperature_c: Optional[float] = None


class OutfitRecommendation(BaseModel):
    item_ids: List[str]
    reason: str
    score: float


class RecommendResponse(BaseModel):
    recommendations: List[OutfitRecommendation]
