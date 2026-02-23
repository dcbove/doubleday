import { useEffect } from "react";
import { View, ActivityIndicator } from "react-native";
import { Slot, router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import useAuth from "../../src/auth/useAuth";
import Navbar from "../../src/components/Navbar";

export default function AuthLayout() {
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [user, loading]);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator size="large" color="#6b7280" />
      </View>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <SafeAreaView className="flex-1 bg-gray-50" edges={["top"]}>
      <Navbar />
      <View className="mx-auto w-full max-w-7xl flex-1 px-3 py-4 sm:px-6 sm:py-8 lg:px-8">
        <Slot />
      </View>
    </SafeAreaView>
  );
}
