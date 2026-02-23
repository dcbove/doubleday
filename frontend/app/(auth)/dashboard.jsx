import { View, Text } from "react-native";
import useCatalog from "../../src/hooks/useCatalog";
import PlayerSearch from "../../src/components/PlayerSearch";

const DEFAULT_ROLE = "pitchers";
const DEFAULT_SEASON = 2025;

export default function Dashboard() {
  const { catalog, manifest, loading, error, search } = useCatalog(
    DEFAULT_ROLE,
    DEFAULT_SEASON,
  );

  return (
    <View>
      <Text className="text-2xl font-bold text-gray-900">Dashboard</Text>
      <Text className="mt-2 text-gray-600">Welcome to Doubleday.</Text>

      {manifest && (
        <Text className="mt-1 text-xs text-gray-400">
          {manifest.counts.players} players · Data through{" "}
          {manifest.coverage.last_game_date_seen}
        </Text>
      )}

      <View className="mt-6">
        <PlayerSearch
          catalog={catalog}
          loading={loading}
          error={error}
          search={search}
        />
      </View>
    </View>
  );
}
