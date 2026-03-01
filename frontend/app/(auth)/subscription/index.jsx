import { useState } from "react";
import { View, Text, Pressable, ActivityIndicator, Platform } from "react-native";
import * as Linking from "expo-linking";
import useSubscription from "../../../src/hooks/useSubscription";
import { apiPost } from "../../../src/api/client";

export default function Subscription() {
  const { subscription, loading, refresh } = useSubscription();
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleCheckout() {
    setActionLoading(true);
    setError(null);
    try {
      const data = await apiPost("/subscriptions/checkout");
      if (Platform.OS === "web") {
        window.location.href = data.checkout_url;
      } else {
        Linking.openURL(data.checkout_url);
      }
    } catch (err) {
      setError(err.message || "Failed to start checkout");
      setActionLoading(false);
    }
  }

  async function handlePortal() {
    setActionLoading(true);
    setError(null);
    try {
      const data = await apiPost("/subscriptions/portal");
      if (Platform.OS === "web") {
        window.location.href = data.portal_url;
      } else {
        Linking.openURL(data.portal_url);
      }
    } catch (err) {
      setError(err.message || "Failed to open portal");
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator size="large" color="#6b7280" />
      </View>
    );
  }

  const isActive = subscription?.status === "active";

  return (
    <View className="flex-1 px-4">
      <Text className="text-2xl font-bold text-gray-900">Subscription</Text>

      {error && (
        <View className="mt-4 rounded-lg bg-red-50 p-3">
          <Text className="text-sm text-red-700">{error}</Text>
        </View>
      )}

      {isActive ? (
        <View className="mt-6">
          <View className="rounded-lg border border-green-200 bg-green-50 p-4">
            <Text className="text-lg font-semibold text-green-800">Active</Text>
            {subscription.tier && (
              <Text className="mt-1 text-sm text-green-700">
                Plan: {subscription.tier}
              </Text>
            )}
            {subscription.current_period_end && (
              <Text className="mt-1 text-sm text-green-700">
                Renews: {new Date(subscription.current_period_end).toLocaleDateString()}
              </Text>
            )}
          </View>

          <Pressable
            className="mt-4 rounded-lg bg-gray-800 px-6 py-3"
            onPress={handlePortal}
            disabled={actionLoading}
          >
            {actionLoading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text className="text-center text-base font-semibold text-white">
                Manage Subscription
              </Text>
            )}
          </Pressable>
        </View>
      ) : (
        <View className="mt-6">
          <View className="rounded-lg border border-gray-200 bg-white p-4">
            <Text className="text-lg font-semibold text-gray-900">
              No active subscription
            </Text>
            <Text className="mt-1 text-sm text-gray-600">
              Subscribe to access pitch data and analytics.
            </Text>
          </View>

          <Pressable
            className="mt-4 rounded-lg bg-blue-600 px-6 py-3"
            onPress={handleCheckout}
            disabled={actionLoading}
          >
            {actionLoading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text className="text-center text-base font-semibold text-white">
                Subscribe
              </Text>
            )}
          </Pressable>

          {subscription?.status === "canceled" && (
            <Text className="mt-3 text-center text-sm text-gray-500">
              Your subscription was canceled. Subscribe again to regain access.
            </Text>
          )}

          {subscription?.status === "past_due" && (
            <View className="mt-3 rounded-lg bg-yellow-50 p-3">
              <Text className="text-sm text-yellow-700">
                Your payment is past due. Please update your payment method.
              </Text>
              <Pressable
                className="mt-2 rounded bg-yellow-600 px-4 py-2"
                onPress={handlePortal}
              >
                <Text className="text-center text-sm font-semibold text-white">
                  Update Payment
                </Text>
              </Pressable>
            </View>
          )}
        </View>
      )}

      <Pressable className="mt-4" onPress={refresh}>
        <Text className="text-center text-sm text-blue-600">Refresh status</Text>
      </Pressable>
    </View>
  );
}
