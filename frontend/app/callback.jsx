import { useEffect } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { router } from "expo-router";
import { Hub } from "aws-amplify/utils";
import { getCurrentUser } from "aws-amplify/auth";

export default function Callback() {
  useEffect(() => {
    const unsubscribe = Hub.listen("auth", ({ payload }) => {
      if (payload.event === "signInWithRedirect") {
        router.replace("/dashboard");
      }
    });

    // If the user is already signed in (e.g. page refresh), redirect immediately
    getCurrentUser()
      .then(() => router.replace("/dashboard"))
      .catch(() => {});

    return unsubscribe;
  }, []);

  return (
    <View className="flex-1 items-center justify-center">
      <ActivityIndicator size="large" color="#6b7280" />
      <Text className="mt-4 text-gray-500">Signing in...</Text>
    </View>
  );
}
