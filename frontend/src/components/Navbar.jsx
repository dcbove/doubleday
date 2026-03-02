import { useState, useRef, useEffect } from "react";
import { View, Text, Pressable, Image, Platform } from "react-native";
import { router } from "expo-router";
import useAuth from "../auth/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen || Platform.OS !== "web") return;

    function handlePress(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePress);
    return () => document.removeEventListener("mousedown", handlePress);
  }, [menuOpen]);

  return (
    <View className="border-b border-gray-200 bg-white" style={{ zIndex: 50 }}>
      <View
        className="mx-auto flex w-full max-w-7xl flex-row items-center justify-between px-4 py-3 sm:px-6 lg:px-8"
        style={{ overflow: "visible" }}
      >
        <View className="flex-row items-center gap-6">
          <Pressable onPress={() => router.push("/dashboard")}>
            <Text className="text-lg font-bold text-gray-900">Doubleday</Text>
          </Pressable>
          <Pressable onPress={() => router.push("/dashboard")}>
            <Text className="text-sm text-gray-600">Dashboard</Text>
          </Pressable>
        </View>
        {user && (
          <View ref={menuRef} style={{ position: "relative", overflow: "visible", zIndex: 50 }}>
            <Pressable
              className="flex-row items-center gap-2 rounded-md px-2 py-1.5"
              onPress={() => setMenuOpen((prev) => !prev)}
            >
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
              <Text className="text-xs text-gray-400">▼</Text>
            </Pressable>

            {menuOpen && (
              <View
                style={{
                  position: "absolute",
                  right: Platform.OS === "web" ? undefined : 0,
                  left: Platform.OS === "web" ? 0 : undefined,
                  top: "100%",
                  marginTop: 4,
                  width: 192,
                  backgroundColor: "white",
                  borderRadius: 8,
                  borderWidth: 1,
                  borderColor: "#e5e7eb",
                  shadowColor: "#000",
                  shadowOffset: { width: 0, height: 4 },
                  shadowOpacity: 0.1,
                  shadowRadius: 6,
                  elevation: 8,
                  paddingVertical: 4,
                  zIndex: 50,
                }}
              >
                <Pressable
                  onPress={() => {
                    setMenuOpen(false);
                    router.push("/subscription");
                  }}
                >
                  {({ pressed }) => (
                    <Text
                      style={{
                        paddingHorizontal: 16,
                        paddingVertical: 8,
                        fontSize: 14,
                        color: "#374151",
                        backgroundColor: pressed ? "#f3f4f6" : "transparent",
                      }}
                    >
                      Subscription
                    </Text>
                  )}
                </Pressable>
                <View
                  style={{
                    marginHorizontal: 12,
                    marginVertical: 4,
                    borderBottomWidth: 1,
                    borderBottomColor: "#f3f4f6",
                  }}
                />
                <Pressable
                  onPress={() => {
                    setMenuOpen(false);
                    logout();
                  }}
                >
                  {({ pressed }) => (
                    <Text
                      style={{
                        paddingHorizontal: 16,
                        paddingVertical: 8,
                        fontSize: 14,
                        color: "#374151",
                        backgroundColor: pressed ? "#f3f4f6" : "transparent",
                      }}
                    >
                      Sign out
                    </Text>
                  )}
                </Pressable>
              </View>
            )}
          </View>
        )}
      </View>
    </View>
  );
}
