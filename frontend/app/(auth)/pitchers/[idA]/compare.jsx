import { useState, useMemo } from "react";
import { View, Text, Pressable, Image, ScrollView, ActivityIndicator } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import useCatalog from "../../../../src/hooks/useCatalog";
import usePitchData from "../../../../src/hooks/usePitchData";
import PlayerSearch from "../../../../src/components/PlayerSearch";
import CompareMovementChart from "../../../../src/components/CompareMovementChart";
import CompareStatsTable from "../../../../src/components/CompareStatsTable";

/**
 * Pitcher comparison page.
 *
 * Displays two pitcher panels side-by-side with independent season selectors,
 * an overlay movement chart, and a side-by-side stats table. Pitcher A comes
 * from the URL param; Pitcher B is selected via typeahead search on the page.
 */
export default function PitcherCompare() {
  const { idA, pitcherBId: initialBId, seasonA: initialSeasonA, seasonB: initialSeasonB } =
    useLocalSearchParams();
  const pitcherAId = Number(idA);

  const [seasonA, setSeasonA] = useState(
    initialSeasonA ? Number(initialSeasonA) : 2025,
  );
  const [seasonB, setSeasonB] = useState(
    initialSeasonB ? Number(initialSeasonB) : initialSeasonA ? Number(initialSeasonA) : 2025,
  );
  const [pitcherBId, setPitcherBId] = useState(
    initialBId ? Number(initialBId) : null,
  );
  const [pitcherBPlayer, setPitcherBPlayer] = useState(null);
  const [hoveredPitchType, setHoveredPitchType] = useState(null);

  const { catalog: catalogA, loading: catalogALoading } = useCatalog(
    "pitchers",
    seasonA,
  );
  const {
    catalog: catalogB,
    loading: catalogBLoading,
    error: catalogBError,
    search: searchB,
  } = useCatalog("pitchers", seasonB);
  const { pitches: pitchesA, loading: pitchALoading } = usePitchData(
    pitcherAId,
    seasonA,
  );
  const {
    pitches: pitchesB,
    loading: pitchBLoading,
    error: pitchBError,
  } = usePitchData(pitcherBId, seasonB);

  const playerA = useMemo(() => {
    if (!catalogA) return null;
    return catalogA.players.find((p) => p.id === pitcherAId) || null;
  }, [catalogA, pitcherAId]);

  const teamA = useMemo(() => {
    if (!catalogA || !playerA) return null;
    return catalogA.teams[String(playerA.team_season_id)] || null;
  }, [catalogA, playerA]);

  const playerB = useMemo(() => {
    if (pitcherBPlayer) {
      if (!catalogB) return pitcherBPlayer;
      return (
        catalogB.players.find((p) => p.id === pitcherBId) || pitcherBPlayer
      );
    }
    if (pitcherBId && catalogB) {
      return catalogB.players.find((p) => p.id === pitcherBId) || null;
    }
    return null;
  }, [catalogB, pitcherBId, pitcherBPlayer]);

  const teamB = useMemo(() => {
    if (!catalogB || !playerB) return null;
    return catalogB.teams[String(playerB.team_season_id)] || null;
  }, [catalogB, playerB]);

  const sortedA = useMemo(() => {
    if (!pitchesA) return null;
    return [...pitchesA].sort((a, b) => b.usage_rate - a.usage_rate);
  }, [pitchesA]);

  const sortedB = useMemo(() => {
    if (!pitchesB) return null;
    return [...pitchesB].sort((a, b) => b.usage_rate - a.usage_rate);
  }, [pitchesB]);

  function handleSelectB(player) {
    setPitcherBId(player.id);
    setPitcherBPlayer(player);
  }

  function handleChangeB() {
    setPitcherBId(null);
    setPitcherBPlayer(null);
  }

  const bothReady =
    sortedA && sortedA.length > 0 && sortedB && sortedB.length > 0;

  return (
    <ScrollView className="flex-1">
      <Pressable
        onPress={() => router.push(`/pitchers/${idA}`)}
        className="mb-4 hidden sm:flex"
      >
        <Text className="text-sm text-gray-500">{"\u2190"} Back to Pitcher</Text>
      </Pressable>

      {/* Pitcher panels */}
      <View className="flex flex-col gap-4 sm:flex-row sm:gap-6">
        {/* Pitcher A panel */}
        <View className="flex-1">
          {catalogALoading && (
            <ActivityIndicator size="small" color="#9ca3af" />
          )}
          {playerA && (
            <View className="flex-row items-center gap-3">
              <Image
                source={{ uri: playerA.headshot_url }}
                className="h-12 w-12 rounded-full bg-gray-100"
                resizeMode="cover"
              />
              <View>
                <View className="flex-row items-center gap-1.5">
                  <View className="h-3 w-3 rounded-full bg-gray-500" />
                  <Text className="text-base font-bold text-gray-900 sm:text-lg">
                    {playerA.first} {playerA.last}
                  </Text>
                </View>
                <Text className="text-xs text-gray-600">
                  {teamA?.abbr || "\u2014"} · {playerA.pos || "\u2014"}
                </Text>
              </View>
            </View>
          )}
          <View className="mt-2 flex-row gap-2">
            {[2024, 2025].map((s) => (
              <Pressable
                key={s}
                onPress={() => setSeasonA(s)}
                className={`rounded-md px-3 py-1.5 sm:px-4 sm:py-2 ${
                  seasonA === s
                    ? "bg-blue-600"
                    : "bg-gray-100 active:bg-gray-200"
                }`}
              >
                <Text
                  className={`text-xs font-medium sm:text-sm ${
                    seasonA === s ? "text-white" : "text-gray-700"
                  }`}
                >
                  {s}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Pitcher B panel */}
        <View className="flex-1">
          {pitcherBId && playerB ? (
            <View>
              <View className="flex-row items-center gap-3">
                <Image
                  source={{ uri: playerB.headshot_url }}
                  className="h-12 w-12 rounded-full bg-gray-100"
                  resizeMode="cover"
                />
                <View className="min-w-0 flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <View className="h-3 w-3 rounded-full border-2 border-gray-500 bg-white" />
                    <Text className="text-base font-bold text-gray-900 sm:text-lg">
                      {playerB.first} {playerB.last}
                    </Text>
                  </View>
                  <Text className="text-xs text-gray-600">
                    {teamB?.abbr || "\u2014"} · {playerB.pos || "\u2014"}
                  </Text>
                </View>
                <Pressable
                  onPress={handleChangeB}
                  className="rounded-md border border-gray-300 px-2 py-1 active:bg-gray-50"
                >
                  <Text className="text-xs font-medium text-gray-700">
                    Change
                  </Text>
                </Pressable>
              </View>
              <View className="mt-2 flex-row gap-2">
                {[2024, 2025].map((s) => (
                  <Pressable
                    key={s}
                    onPress={() => setSeasonB(s)}
                    className={`rounded-md px-3 py-1.5 sm:px-4 sm:py-2 ${
                      seasonB === s
                        ? "bg-blue-600"
                        : "bg-gray-100 active:bg-gray-200"
                    }`}
                  >
                    <Text
                      className={`text-xs font-medium sm:text-sm ${
                        seasonB === s ? "text-white" : "text-gray-700"
                      }`}
                    >
                      {s}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : (
            <PlayerSearch
              catalog={catalogB}
              loading={catalogBLoading}
              error={catalogBError}
              search={searchB}
              onSelect={handleSelectB}
            />
          )}
        </View>
      </View>

      {/* Loading / error states */}
      {(pitchALoading || pitchBLoading) && pitcherBId && (
        <View className="mt-6">
          <ActivityIndicator size="small" color="#9ca3af" />
        </View>
      )}
      {pitchBError && (
        <Text className="mt-6 text-sm text-red-600">{pitchBError}</Text>
      )}

      {/* Chart and table */}
      {bothReady && playerA && playerB && (
        <View className="mt-3 gap-3 sm:mt-6 sm:gap-6">
          <CompareMovementChart
            pitchesA={sortedA}
            pitchesB={sortedB}
            playerA={playerA}
            playerB={playerB}
            seasonA={seasonA}
            seasonB={seasonB}
            hoveredPitchType={hoveredPitchType}
            onHover={setHoveredPitchType}
          />
          <CompareStatsTable
            pitchesA={sortedA}
            pitchesB={sortedB}
            playerA={playerA}
            playerB={playerB}
            seasonA={seasonA}
            seasonB={seasonB}
            hoveredPitchType={hoveredPitchType}
            onHover={setHoveredPitchType}
          />
        </View>
      )}

      {/* No data messages */}
      {sortedA && sortedA.length === 0 && (
        <Text className="mt-6 text-sm text-gray-500">
          No pitch data for Pitcher A in {seasonA}.
        </Text>
      )}
      {pitcherBId && sortedB && sortedB.length === 0 && (
        <Text className="mt-6 text-sm text-gray-500">
          No pitch data for Pitcher B in {seasonB}.
        </Text>
      )}
    </ScrollView>
  );
}
