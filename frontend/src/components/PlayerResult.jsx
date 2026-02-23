import { View, Text, Pressable, Image } from "react-native";
import { Link } from "expo-router";

/**
 * Single player result row in the typeahead dropdown.
 *
 * When `onSelect` is provided, renders a Pressable that calls `onSelect(player)`
 * instead of navigating via Link. Same visual layout either way.
 *
 * @param {{ player: object, teams: object, onSelect?: function }} props
 */
export default function PlayerResult({ player, teams, onSelect }) {
  const team = teams[String(player.team_season_id)] || {};

  const inner = (
    <View className="flex-row items-center gap-3 px-3 py-2">
      <Image
        source={{ uri: player.headshot_url }}
        className="h-10 w-10 rounded-full bg-gray-100"
        resizeMode="cover"
      />
      <View className="min-w-0 flex-1">
        <Text className="text-sm font-medium text-gray-900" numberOfLines={1}>
          {player.first} {player.last}
        </Text>
        <Text className="text-xs text-gray-500">
          {team.abbr || "\u2014"} · {player.pos || "\u2014"} ·{" "}
          {player.bats}/{player.throws}
        </Text>
      </View>
    </View>
  );

  if (onSelect) {
    return (
      <Pressable
        onPress={() => onSelect(player)}
        className="active:bg-gray-50"
      >
        {inner}
      </Pressable>
    );
  }

  return (
    <Link href={`/pitchers/${player.id}`} asChild>
      <Pressable className="active:bg-gray-50">{inner}</Pressable>
    </Link>
  );
}
