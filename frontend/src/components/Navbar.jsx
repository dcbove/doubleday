import { useState, useRef, useEffect, useCallback } from "react";
import { View, Text, Pressable, Image } from "react-native";
import { router } from "expo-router";
import useAuth from "../auth/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useEffect(() => {
    if (!menuOpen) return;

    function handleClick(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
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
          <View ref={menuRef} style={{ position: "relative", overflow: "visible" }}>
            <Pressable
              className="flex-row items-center gap-2 rounded-md px-2 py-1.5 active:bg-gray-100"
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
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  top: "100%",
                  marginTop: 4,
                  width: 192,
                  backgroundColor: "white",
                  borderRadius: 8,
                  border: "1px solid #e5e7eb",
                  boxShadow: "0 4px 6px -1px rgba(0,0,0,.1)",
                  paddingTop: 4,
                  paddingBottom: 4,
                  zIndex: 50,
                }}
              >
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    closeMenu();
                    router.push("/subscription");
                  }}
                  style={{
                    padding: "8px 16px",
                    cursor: "pointer",
                    fontSize: 14,
                    color: "#374151",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor = "#f3f4f6")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                >
                  Subscription
                </div>
                <div
                  style={{
                    margin: "4px 12px",
                    borderBottom: "1px solid #f3f4f6",
                  }}
                />
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    closeMenu();
                    logout();
                  }}
                  style={{
                    padding: "8px 16px",
                    cursor: "pointer",
                    fontSize: 14,
                    color: "#374151",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor = "#f3f4f6")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                >
                  Sign out
                </div>
              </div>
            )}
          </View>
        )}
      </View>
    </View>
  );
}
