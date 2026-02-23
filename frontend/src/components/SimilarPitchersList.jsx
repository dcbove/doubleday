import { useMemo } from "react";
import { View, Text, Image, ScrollView, Pressable } from "react-native";
import { Link } from "expo-router";

/**
 * Compact scrollable list of similar pitchers based on shape-similarity scores.
 *
 * Resolves pitcher names and teams from the catalog. Each row links to the
 * compare page with the neighbor pre-selected as Pitcher B.
 */
export default function SimilarPitchersList({
  neighbors,
  catalog,
  sourcePitcherId,
  sourceSeason,
  maxHeight,
}) {
  const rows = useMemo(() => {
    if (!neighbors || !catalog) return [];
    return neighbors.map((n) => {
      const player = catalog.players.find(
        (p) => p.id === n.neighbor_pitcher,
      );
      const team = player
        ? catalog.teams[String(player.team_season_id)]
        : null;
      return { ...n, player, team };
    });
  }, [neighbors, catalog]);

  if (rows.length === 0) return null;

  return (
    <View className="rounded-lg border border-gray-200" style={{ overflow: "hidden", flex: maxHeight ? undefined : 1 }}>
      <ScrollView style={maxHeight ? { maxHeight } : undefined}>
        {rows.map((row, idx) => (
          <View key={`${row.neighbor_pitcher}-${row.neighbor_season}`}>
            {idx > 0 && <View className="border-b border-gray-100" />}
            <Link
              href={{
                pathname: `/pitchers/${sourcePitcherId}/compare`,
                params: {
                  pitcherBId: row.neighbor_pitcher,
                  seasonA: sourceSeason,
                  seasonB: row.neighbor_season,
                },
              }}
              asChild
            >
              <Pressable className="flex-row items-center gap-1.5 px-2 py-1 active:bg-gray-50 sm:gap-2 sm:px-3 sm:py-1.5">
                {/* Rank */}
                <Text className="w-4 text-center text-[9px] font-semibold text-gray-400 sm:text-[11px]">
                  {row.rank}
                </Text>

                {/* Headshot */}
                {row.player ? (
                  <Image
                    source={{ uri: row.player.headshot_url }}
                    className="h-5 w-5 rounded-full bg-gray-100 sm:h-6 sm:w-6"
                    resizeMode="cover"
                  />
                ) : (
                  <View className="h-5 w-5 rounded-full bg-gray-200 sm:h-6 sm:w-6" />
                )}

                {/* Name + team */}
                <View className="min-w-0 flex-1">
                  <Text
                    className="text-[10px] font-medium text-gray-900 sm:text-xs"
                    numberOfLines={1}
                  >
                    {row.player
                      ? `${row.player.first} ${row.player.last}`
                      : `Pitcher #${row.neighbor_pitcher}`}
                  </Text>
                  <Text
                    className="text-[9px] leading-tight text-gray-500 sm:text-[11px]"
                    numberOfLines={1}
                  >
                    {row.team?.abbr || "\u2014"} · {row.neighbor_season}
                  </Text>
                </View>

                {/* Similarity score */}
                <Text className="text-[9px] text-gray-500 sm:text-[11px]">
                  {(row.similarity_score * 100).toFixed(1)}%
                </Text>
              </Pressable>
            </Link>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}
