import { useEffect } from "react";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  ImageBackground,
} from "react-native";
import { router } from "expo-router";
import useAuth from "../src/auth/useAuth";

const loginBg = require("../assets/login-bg.png");

export default function Landing() {
  const { user, loading, login } = useAuth();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [loading, user]);

  if (loading || user) {
    return (
      <View className="flex-1 items-center justify-center bg-gray-900">
        <ActivityIndicator size="large" color="#ef4444" />
      </View>
    );
  }

  return (
    <ImageBackground
      source={loginBg}
      resizeMode="cover"
      className="flex-1"
    >
      <View className="flex-1 items-center justify-end bg-black/40 pb-24">
        <View className="items-center">
          <Text className="mb-2 text-5xl font-bold text-white">Doubleday</Text>
          <Text className="mb-10 text-lg text-gray-300">
            Statcast pitch analytics
          </Text>
          <Pressable
            onPress={login}
            className="rounded-lg bg-red-600 px-8 py-4 active:bg-red-700"
          >
            <Text className="text-lg font-semibold text-white">
              Sign in with Google
            </Text>
          </Pressable>
        </View>
      </View>
    </ImageBackground>
  );
}
