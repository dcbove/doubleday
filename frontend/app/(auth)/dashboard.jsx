import { View, Text, Pressable } from "react-native";
import { router } from "expo-router";
import useCatalog from "../../src/hooks/useCatalog";
import useSubscription from "../../src/hooks/useSubscription";
import PlayerSearch from "../../src/components/PlayerSearch";

const DEFAULT_ROLE = "pitchers";
const DEFAULT_SEASON = 2025;

export default function Dashboard() {
  const { catalog, manifest, loading, error, search } = useCatalog(
    DEFAULT_ROLE,
    DEFAULT_SEASON,
  );
  const { subscription, loading: subLoading } = useSubscription();

  const isActive = subscription?.status === "active";

  return (
    <View>
      {!subLoading && !isActive && (
        <Pressable
          className="mb-6 flex-row items-center rounded-lg border border-amber-300 bg-amber-50 px-4 py-3"
          onPress={() => router.push("/subscription")}
        >
          <Text className="flex-1 text-sm text-amber-900">
            Subscribe to unlock pitch data and analytics.
          </Text>
          <Text className="text-sm font-semibold text-amber-700">
            Subscribe →
          </Text>
        </Pressable>
      )}

      <View className="flex-row flex-wrap gap-4">
        <View className="min-w-[300px] flex-1 rounded-xl border border-gray-200 bg-white shadow-sm">
          <View className="rounded-t-xl bg-gray-900 px-5 py-4">
            <Text className="text-lg font-bold text-white">
              Pitcher Analytics
            </Text>
            {manifest && (
              <Text className="mt-1 text-xs text-gray-400">
                {manifest.counts.players} players · Data through{" "}
                {manifest.coverage.last_game_date_seen}
              </Text>
            )}
          </View>
          <View className="px-5 py-4">
            <PlayerSearch
              catalog={catalog}
              loading={loading}
              error={error}
              search={search}
              onSelect={
                isActive
                  ? undefined
                  : () => router.push("/subscription")
              }
            />
          </View>
        </View>

        <View className="min-w-[300px] flex-1 rounded-xl border border-gray-200 bg-white shadow-sm">
          <View className="rounded-t-xl bg-gray-900 px-5 py-4">
            <Text className="text-lg font-bold text-white">Betting Buddy</Text>
            <Text className="mt-1 text-xs text-gray-400">Coming soon</Text>
          </View>
          <View className="items-center justify-center px-5 py-12">
            <Text className="text-3xl">🎰</Text>
            <Text className="mt-3 text-center text-sm text-gray-400">
              AI-powered betting insights are on the way.
            </Text>
          </View>
        </View>
      </View>
    </View>
  );
}
