import { View, Text, Pressable } from "react-native";
import { router } from "expo-router";

export default function SubscriptionCancel() {
  return (
    <View className="flex-1 items-center justify-center px-6">
      <Text className="text-2xl font-bold text-gray-900">
        Checkout Canceled
      </Text>
      <Text className="mt-3 text-center text-gray-600">
        No charges were made. You can subscribe anytime.
      </Text>
      <Pressable
        className="mt-6 rounded-lg bg-blue-600 px-6 py-3"
        onPress={() => router.replace("/subscription")}
      >
        <Text className="text-base font-semibold text-white">Try Again</Text>
      </Pressable>
      <Pressable
        className="mt-3"
        onPress={() => router.replace("/dashboard")}
      >
        <Text className="text-sm text-blue-600">Back to Dashboard</Text>
      </Pressable>
    </View>
  );
}
