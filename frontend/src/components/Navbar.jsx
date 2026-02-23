import { View, Text, Pressable, Image } from "react-native";
import { router } from "expo-router";
import useAuth from "../auth/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <View className="border-b border-gray-200 bg-white">
      <View className="mx-auto flex w-full max-w-7xl flex-row items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <View className="flex-row items-center gap-6">
          <Pressable onPress={() => router.push("/dashboard")}>
            <Text className="text-lg font-bold text-gray-900">Doubleday</Text>
          </Pressable>
          <Pressable onPress={() => router.push("/dashboard")}>
            <Text className="text-sm text-gray-600">Dashboard</Text>
          </Pressable>
        </View>
        <View className="flex-row items-center gap-4">
          {user && (
            <View className="flex-row items-center gap-2">
              {user.picture && (
                <Image
                  source={{ uri: user.picture }}
                  className="h-7 w-7 rounded-full"
                  referrerPolicy="no-referrer"
                />
              )}
              <Text className="hidden text-sm text-gray-600 sm:flex">
                {user.name}
              </Text>
            </View>
          )}
          <Pressable
            onPress={logout}
            className="rounded-md bg-gray-100 px-3 py-1.5 active:bg-gray-200"
          >
            <Text className="text-sm text-gray-700">Sign out</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}
