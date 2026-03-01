import { useEffect, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { router } from "expo-router";
import useSubscription from "../../../src/hooks/useSubscription";

export default function SubscriptionSuccess() {
  const { subscription, loading, refresh } = useSubscription();
  const [pollCount, setPollCount] = useState(0);

  useEffect(() => {
    if (loading) return;

    if (subscription?.status === "active") {
      const timer = setTimeout(() => router.replace("/dashboard"), 2000);
      return () => clearTimeout(timer);
    }

    if (pollCount < 10) {
      const timer = setTimeout(() => {
        refresh();
        setPollCount((c) => c + 1);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [subscription, loading, pollCount, refresh]);

  if (subscription?.status === "active") {
    return (
      <View className="flex-1 items-center justify-center px-6">
        <Text className="text-2xl font-bold text-green-700">
          Subscription Active
        </Text>
        <Text className="mt-3 text-center text-gray-600">
          Redirecting to dashboard...
        </Text>
      </View>
    );
  }

  return (
    <View className="flex-1 items-center justify-center px-6">
      <ActivityIndicator size="large" color="#6b7280" />
      <Text className="mt-4 text-lg font-semibold text-gray-900">
        Processing Payment
      </Text>
      <Text className="mt-2 text-center text-gray-600">
        Please wait while we confirm your subscription...
      </Text>
    </View>
  );
}
