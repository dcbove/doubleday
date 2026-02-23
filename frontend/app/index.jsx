import { useEffect } from "react";
import { View, Text, Pressable, ActivityIndicator } from "react-native";
import { router } from "expo-router";
import useAuth from "../src/auth/useAuth";

export default function Landing() {
  const { user, loading, login } = useAuth();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [loading, user]);

  if (loading || user) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator size="large" color="#6b7280" />
      </View>
    );
  }

  return (
    <View className="flex-1 items-center justify-center bg-gray-50">
      <View className="items-center">
        <Text className="mb-2 text-4xl font-bold text-gray-900">Doubleday</Text>
        <Text className="mb-8 text-gray-600">Statcast pitch analytics</Text>
        <Pressable
          onPress={login}
          className="rounded-lg bg-blue-600 px-6 py-3 active:bg-blue-700"
        >
          <Text className="font-medium text-white">Sign in with Google</Text>
        </Pressable>
      </View>
    </View>
  );
}
