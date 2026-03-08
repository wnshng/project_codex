import { Tabs } from "expo-router";
import { Shirt, Sparkles } from "lucide-react-native";

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen
        name="closet"
        options={{
          title: "Closet",
          tabBarIcon: ({ color, size }) => <Shirt color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="recommend"
        options={{
          title: "Recommend",
          tabBarIcon: ({ color, size }) => <Sparkles color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
