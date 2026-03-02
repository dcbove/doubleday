import { useState, useMemo } from "react";
import { View, Text } from "react-native";
import SearchInput from "./SearchInput";
import PlayerResult from "./PlayerResult";

/**
 * Player typeahead search component.
 *
 * Renders a search input and a filtered list of matching players from the
 * catalog. Results appear after the user types at least 2 characters.
 *
 * When `onSelect` is provided, each result calls `onSelect(player)` instead
 * of navigating, and the query is cleared after selection.
 *
 * @param {{ catalog: object|null, loading: boolean, error: string|null, search: function, onSelect?: function }} props
 */
export default function PlayerSearch({ catalog, loading, error, search, onSelect }) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    if (query.length < 2) return [];
    return search(query);
  }, [query, search]);

  return (
    <View className="w-full max-w-md">
      <Text className="mb-1 text-sm font-medium text-gray-700">
        Search pitchers
      </Text>
      <SearchInput
        value={query}
        onChange={setQuery}
        loading={loading}
        placeholder="Search by last name..."
      />

      {error && <Text className="mt-2 text-sm text-red-600">{error}</Text>}

      {!loading && catalog && query.length >= 2 && (
        <View className="mt-1 rounded-md border border-gray-200 bg-white shadow-sm">
          {results.length === 0 ? (
            <Text className="px-3 py-2 text-sm text-gray-500">
              No players found.
            </Text>
          ) : (
            <View>
              {results.map((item, idx) => (
                <View key={String(item.player_id)}>
                  {idx > 0 && <View className="border-b border-gray-100" />}
                  <PlayerResult
                    player={item}
                    onSelect={
                      onSelect
                        ? (p) => {
                            onSelect(p);
                            setQuery("");
                          }
                        : undefined
                    }
                  />
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
}
