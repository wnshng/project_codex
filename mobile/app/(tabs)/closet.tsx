import { useMemo } from "react";
import { FlatList, Text, View } from "react-native";

type ClosetCard = {
  id: string;
  name: string;
  colorHex: string;
  category: string;
};

const MOCK_ITEMS: ClosetCard[] = [
  { id: "1", name: "White Oxford Shirt", colorHex: "#F5F5F5", category: "top" },
  { id: "2", name: "Navy Slacks", colorHex: "#1D3557", category: "bottom" },
  { id: "3", name: "Camel Coat", colorHex: "#C19A6B", category: "outer" },
];

export default function ClosetScreen() {
  const empty = useMemo(() => MOCK_ITEMS.length === 0, []);

  return (
    <View className="flex-1 bg-zinc-50 px-5 pt-16">
      <Text className="text-3xl font-bold text-zinc-900">My Closet</Text>
      <Text className="mt-1 text-zinc-500">사진/텍스트로 등록한 아이템을 관리하세요.</Text>

      {empty ? (
        <View className="mt-10 rounded-2xl bg-white p-6">
          <Text className="text-zinc-600">아직 등록된 옷이 없습니다.</Text>
        </View>
      ) : (
        <FlatList
          contentContainerStyle={{ paddingVertical: 20, gap: 12 }}
          data={MOCK_ITEMS}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View className="rounded-2xl bg-white p-4">
              <View className="flex-row items-center justify-between">
                <Text className="text-lg font-semibold text-zinc-900">{item.name}</Text>
                <View className="h-6 w-6 rounded-full" style={{ backgroundColor: item.colorHex }} />
              </View>
              <Text className="mt-1 text-zinc-500">{item.category}</Text>
              <Text className="mt-2 text-xs text-zinc-400">{item.colorHex}</Text>
            </View>
          )}
        />
      )}
    </View>
  );
}
