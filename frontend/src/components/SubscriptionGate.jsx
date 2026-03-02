import { View, Text, Pressable, ActivityIndicator } from "react-native";
import { router } from "expo-router";
import useSubscription from "../hooks/useSubscription";

/**
 * Gate component that checks subscription status before rendering children.
 *
 * If the user has an active subscription, renders children normally. Otherwise,
 * shows a prompt to subscribe with a link to the subscription page.
 */
export default function SubscriptionGate({ children }) {
  const { subscription, loading } = useSubscription();

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator size="large" color="#6b7280" />
        <Text className="mt-3 text-sm text-gray-500">
          Checking subscription...
        </Text>
      </View>
    );
  }

  if (subscription?.status === "active") {
    return children;
  }

  return (
    <View className="flex-1 items-center justify-center px-6">
      <Text className="text-2xl font-bold text-gray-900">
        Subscription Required
      </Text>
      <Text className="mt-3 text-center text-gray-600">
        Access to pitch data and analytics requires an active subscription.
      </Text>
      <Pressable
        className="mt-6 rounded-lg bg-blue-600 px-6 py-3"
        onPress={() => router.push("/subscription")}
      >
        <Text className="text-base font-semibold text-white">Subscribe</Text>
      </Pressable>
    </View>
  );
}
