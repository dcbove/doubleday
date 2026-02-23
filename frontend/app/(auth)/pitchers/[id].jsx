import { useState, useMemo } from "react";
import { View, Text, Pressable, Image, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native";
import { useLocalSearchParams, Link, router } from "expo-router";
import useCatalog from "../../../src/hooks/useCatalog";
import usePitchData from "../../../src/hooks/usePitchData";
import useNeighborData from "../../../src/hooks/useNeighborData";
import PitchMovementChart from "../../../src/components/PitchMovementChart";
import PitchStatsTable from "../../../src/components/PitchStatsTable";
import SimilarPitchersList from "../../../src/components/SimilarPitchersList";

/**
 * Pitcher detail page showing profile info and an interactive pitch movement chart.
 *
 * Reads the pitcher ID from the URL, resolves name and team from the catalog,
 * fetches pitch aggregation data from the API, and renders a scatter plot of
 * pitch movement with a hoverable stat panel.
 */
export default function PitcherDetail() {
  const { id } = useLocalSearchParams();
  const pitcherId = Number(id);
  const [season, setSeason] = useState(2025);
  const [hoveredPitchType, setHoveredPitchType] = useState(null);
  const { width } = useWindowDimensions();
  const isWide = width >= 640;

  const { catalog, loading: catalogLoading } = useCatalog("pitchers", season);
  const { pitches, loading: pitchLoading, error: pitchError } = usePitchData(
    pitcherId,
    season,
  );
  const { neighbors, loading: neighborsLoading } = useNeighborData(
    pitcherId,
    season,
  );

  const player = useMemo(() => {
    if (!catalog) return null;
    return catalog.players.find((p) => p.id === pitcherId) || null;
  }, [catalog, pitcherId]);

  const team = useMemo(() => {
    if (!catalog || !player) return null;
    return catalog.teams[String(player.team_season_id)] || null;
  }, [catalog, player]);

  const sortedPitches = useMemo(() => {
    if (!pitches) return null;
    return [...pitches].sort((a, b) => b.usage_rate - a.usage_rate);
  }, [pitches]);

  return (
    <ScrollView className="flex-1">
      <Pressable
        onPress={() => router.push("/dashboard")}
        className="mb-4 hidden sm:flex"
      >
        <Text className="text-sm text-gray-500">{"\u2190"} Back to Dashboard</Text>
      </Pressable>

      {/* Two-column layout on wider screens */}
      <View className="flex flex-col gap-4 sm:flex-row sm:gap-6">
        {/* Left column: pitcher info, season toggle, graph */}
        <View className="sm:w-[400px]">
          {/* Pitcher header */}
          {catalogLoading && (
            <ActivityIndicator size="small" color="#9ca3af" />
          )}
          {!catalogLoading && !player && (
            <View>
              <Text className="text-2xl font-bold text-gray-900">
                Pitcher not found
              </Text>
              <Text className="mt-2 text-sm text-gray-500">
                No pitcher with ID {pitcherId} in the {season} catalog.
              </Text>
            </View>
          )}
          {player && (
            <View className="flex-row items-center gap-3 sm:gap-4">
              <Image
                source={{ uri: player.headshot_url }}
                className="h-12 w-12 rounded-full bg-gray-100 sm:h-20 sm:w-20"
                resizeMode="cover"
              />
              <View>
                <Text className="text-lg font-bold text-gray-900 sm:text-2xl">
                  {player.first} {player.last}
                </Text>
                <Text className="text-xs text-gray-600 sm:text-sm">
                  {team?.abbr || "\u2014"} · {player.pos || "\u2014"} · B/T:{" "}
                  {player.bats}/{player.throws}
                </Text>
              </View>
            </View>
          )}

          {/* Season toggle + Compare button */}
          <View className="mt-2 flex-row items-center gap-2 sm:mt-4">
            {[2024, 2025].map((s) => (
              <Pressable
                key={s}
                onPress={() => setSeason(s)}
                className={`rounded-md px-3 py-1.5 sm:px-4 sm:py-2 ${
                  season === s
                    ? "bg-blue-600"
                    : "bg-gray-100 active:bg-gray-200"
                }`}
              >
                <Text
                  className={`text-xs font-medium sm:text-sm ${
                    season === s ? "text-white" : "text-gray-700"
                  }`}
                >
                  {s}
                </Text>
              </Pressable>
            ))}
            <Link
              href={{
                pathname: `/pitchers/${id}/compare`,
                params: { seasonA: season },
              }}
              asChild
            >
              <Pressable className="rounded-md border border-gray-300 px-3 py-1.5 active:bg-gray-50 sm:px-4 sm:py-2">
                <Text className="text-xs font-medium text-gray-700 sm:text-sm">
                  Compare
                </Text>
              </Pressable>
            </Link>
          </View>

          {/* Pitch movement chart */}
          {pitchLoading && (
            <View className="mt-6">
              <ActivityIndicator size="small" color="#9ca3af" />
            </View>
          )}
          {pitchError && (
            <Text className="mt-6 text-sm text-red-600">{pitchError}</Text>
          )}
          {sortedPitches && sortedPitches.length === 0 && (
            <Text className="mt-6 text-sm text-gray-500">
              No pitch data available for {season}.
            </Text>
          )}
          {sortedPitches && sortedPitches.length > 0 && (
            <View className="mt-3 sm:mt-6">
              <PitchMovementChart
                pitches={sortedPitches}
                hoveredPitchType={hoveredPitchType}
                onHover={setHoveredPitchType}
              />
            </View>
          )}
        </View>

        {/* Right column: similar pitchers */}
        <View className="min-w-0 sm:flex-1" style={{ maxHeight: isWide ? 500 : 200 }}>
          {neighborsLoading && (
            <ActivityIndicator size="small" color="#9ca3af" />
          )}
          {neighbors && neighbors.length > 0 && (
            <View className="flex-1">
              <Text className="mb-1.5 text-sm font-semibold text-gray-900">
                Most Similar Pitchers
              </Text>
              <SimilarPitchersList
                neighbors={neighbors}
                catalog={catalog}
                sourcePitcherId={pitcherId}
                sourceSeason={season}
              />
            </View>
          )}
        </View>
      </View>

      {/* Stats table — full width below */}
      {sortedPitches && sortedPitches.length > 0 && (
        <View className="mt-3 sm:mt-6">
          <PitchStatsTable
            pitches={sortedPitches}
            hoveredPitchType={hoveredPitchType}
            onHover={setHoveredPitchType}
          />
        </View>
      )}
    </ScrollView>
  );
}
