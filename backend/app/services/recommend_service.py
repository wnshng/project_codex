from __future__ import annotations

import math
from itertools import product
from typing import List

from app.models.schemas import ClothingItem, OutfitRecommendation, RecommendResponse


class RecommendService:
    def recommend(
        self,
        items: List[ClothingItem],
        occasion: str = "casual",
        temperature_c: float | None = None,
    ) -> RecommendResponse:
        tops = [i for i in items if i.category == "top"]
        bottoms = [i for i in items if i.category == "bottom"]
        outers = [i for i in items if i.category == "outer"]

        candidates: list[OutfitRecommendation] = []

        for top, bottom in product(tops, bottoms):
            base_score = self._color_score(top.color_hex, bottom.color_hex)
            warmth_score = self._warmth_score([top, bottom], temperature_c)
            style_score = self._style_score([top, bottom], occasion)

            score = (0.45 * base_score) + (0.25 * warmth_score) + (0.30 * style_score)
            reason = (
                f"Color harmony score={base_score:.2f}, warmth fit={warmth_score:.2f}, "
                f"style fit={style_score:.2f}"
            )
            candidates.append(
                OutfitRecommendation(
                    item_ids=[top.item_id, bottom.item_id],
                    reason=reason,
                    score=round(score, 3),
                )
            )

            for outer in outers:
                layered_warmth = self._warmth_score([top, bottom, outer], temperature_c)
                layered_style = self._style_score([top, bottom, outer], occasion)
                layered_score = (0.4 * base_score) + (0.35 * layered_warmth) + (0.25 * layered_style)
                layered_reason = (
                    f"Layered outfit with balanced contrast, warmth={layered_warmth:.2f}, "
                    f"style={layered_style:.2f}"
                )
                candidates.append(
                    OutfitRecommendation(
                        item_ids=[top.item_id, bottom.item_id, outer.item_id],
                        reason=layered_reason,
                        score=round(layered_score, 3),
                    )
                )

        top_3 = sorted(candidates, key=lambda x: x.score, reverse=True)[:3]
        return RecommendResponse(recommendations=top_3)

    def _color_score(self, hex_a: str, hex_b: str) -> float:
        try:
            rgb_a = self._hex_to_rgb(hex_a)
            rgb_b = self._hex_to_rgb(hex_b)
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb_a, rgb_b)))
            norm = min(dist / 441.67295593, 1.0)
            if 0.25 <= norm <= 0.65:
                return 1.0
            if norm < 0.25:
                return 0.8
            return 0.7
        except Exception:
            return 0.5

    def _warmth_score(self, outfit: List[ClothingItem], temp_c: float | None) -> float:
        if temp_c is None:
            return 0.7
        avg_warmth = sum(i.warmth_level for i in outfit) / len(outfit)
        target = 5 if temp_c < 5 else 4 if temp_c < 14 else 3 if temp_c < 22 else 2
        diff = abs(avg_warmth - target)
        return max(0.0, 1.0 - (diff / 4.0))

    def _style_score(self, outfit: List[ClothingItem], occasion: str) -> float:
        flattened_tags = {tag.lower() for item in outfit for tag in item.style_tags}
        occasion = (occasion or "casual").lower()
        if occasion in flattened_tags:
            return 1.0
        if occasion == "casual" and not flattened_tags:
            return 0.8
        return 0.65

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        if len(value) != 6:
            raise ValueError("Invalid hex color")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
