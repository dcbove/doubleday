import { useState, useMemo } from "react";
import SearchInput from "./SearchInput";
import PlayerResult from "./PlayerResult";

/**
 * Player typeahead search component.
 *
 * Renders a search input and a filtered list of matching players from the
 * catalog. Results appear after the user types at least 2 characters.
 *
 * @param {{ catalog: object|null, loading: boolean, error: string|null, search: function }} props
 */
export default function PlayerSearch({ catalog, loading, error, search }) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    if (query.length < 2) return [];
    return search(query);
  }, [query, search]);

  return (
    <div className="w-full max-w-md">
      <label className="mb-1 block text-sm font-medium text-gray-700">
        Search pitchers
      </label>
      <SearchInput
        value={query}
        onChange={setQuery}
        loading={loading}
        placeholder="Search by last name..."
      />

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {!loading && catalog && query.length >= 2 && (
        <div className="mt-1 rounded-md border border-gray-200 bg-white shadow-sm">
          {results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-gray-500">
              No players found.
            </p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {results.map((player) => (
                <li key={player.id}>
                  <PlayerResult player={player} teams={catalog.teams} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
