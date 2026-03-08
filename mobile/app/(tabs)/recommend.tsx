import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { fetchRecommendations } from "../../src/api/client";

type Recommendation = {
  item_ids: string[];
  reason: string;
  score: number;
};

export default function RecommendScreen() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<Recommendation[]>([]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await fetchRecommendations();
        if (mounted) setItems(data);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <View className="flex-1 bg-zinc-900 px-5 pt-16">
      <Text className="text-3xl font-bold text-white">Today Outfit</Text>
      <Text className="mt-1 text-zinc-300">AI가 추천한 코디 조합입니다.</Text>

      {loading ? (
        <View className="mt-10 items-center">
          <ActivityIndicator size="large" color="#ffffff" />
        </View>
      ) : items.length === 0 ? (
        <View className="mt-8 rounded-2xl bg-zinc-800 p-6">
          <Text className="text-zinc-200">추천 결과가 없습니다.</Text>
        </View>
      ) : (
        <View className="mt-6 gap-3">
          {items.map((rec, idx) => (
            <View key={`${rec.item_ids.join("-")}-${idx}`} className="rounded-2xl bg-zinc-800 p-4">
              <Text className="text-white">{rec.item_ids.join(" + ")}</Text>
              <Text className="mt-1 text-zinc-300">{rec.reason}</Text>
              <Text className="mt-1 text-zinc-400">score: {rec.score}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
