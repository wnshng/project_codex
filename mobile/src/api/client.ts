import axios from "axios";

const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 10000,
});

type RecommendApiResponse = {
  recommendations: Array<{
    item_ids: string[];
    reason: string;
    score: number;
  }>;
};

export async function fetchRecommendations() {
  const payload = {
    items: [
      { item_id: "top-1", category: "top", color_hex: "#F5F5F5", style_tags: ["casual"], season: ["spring"], warmth_level: 2 },
      { item_id: "bottom-1", category: "bottom", color_hex: "#1D3557", style_tags: ["casual"], season: ["spring"], warmth_level: 3 },
      { item_id: "outer-1", category: "outer", color_hex: "#C19A6B", style_tags: ["casual"], season: ["fall"], warmth_level: 4 }
    ],
    occasion: "casual",
    temperature_c: 15
  };

  const response = await api.post<RecommendApiResponse>("/api/recommend", payload);
  return response.data.recommendations;
}
