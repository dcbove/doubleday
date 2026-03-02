import { useEffect, useState, useCallback } from "react";
import { View, Text, Pressable, ActivityIndicator } from "react-native";
import { router } from "expo-router";
import useSubscription from "../../../src/hooks/useSubscription";

const MAX_ATTEMPTS = 15;
const BACKOFF_CAP_MS = 8000;

function getDelay(attempt) {
  return Math.min(1000 * Math.pow(2, attempt), BACKOFF_CAP_MS);
}

export default function SubscriptionSuccess() {
  const { subscription, loading, refresh } = useSubscription();
  const [pollCount, setPollCount] = useState(0);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (loading || timedOut) return;

    if (subscription?.status === "active") {
      const timer = setTimeout(() => router.replace("/dashboard"), 2000);
      return () => clearTimeout(timer);
    }

    if (pollCount < MAX_ATTEMPTS) {
      const delay = getDelay(pollCount);
      const timer = setTimeout(() => {
        refresh();
        setPollCount((c) => c + 1);
      }, delay);
      return () => clearTimeout(timer);
    }

    setTimedOut(true);
  }, [subscription, loading, pollCount, refresh, timedOut]);

  const handleRetry = useCallback(() => {
    setTimedOut(false);
    setPollCount(0);
    refresh();
  }, [refresh]);

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

  if (timedOut) {
    return (
      <View className="flex-1 items-center justify-center px-6">
        <Text className="text-xl font-bold text-gray-900">
          Taking longer than expected
        </Text>
        <Text className="mt-3 text-center text-gray-600">
          Your payment was received but the subscription hasn't activated yet.
          This usually resolves within a minute.
        </Text>
        <Pressable
          className="mt-6 rounded-lg bg-blue-600 px-6 py-3"
          onPress={handleRetry}
        >
          <Text className="text-base font-semibold text-white">
            Check again
          </Text>
        </Pressable>
        <Pressable
          className="mt-3"
          onPress={() => router.replace("/dashboard")}
        >
          <Text className="text-sm text-blue-600">Go to dashboard</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View className="flex-1 items-center justify-center px-6">
      <ActivityIndicator size="large" color="#6b7280" />
      <Text className="mt-4 text-lg font-semibold text-gray-900">
        Confirming your subscription...
      </Text>
      <Text className="mt-2 text-center text-gray-500">
        This may take a moment.
      </Text>
    </View>
  );
}
