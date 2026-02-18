import useCatalog from "../hooks/useCatalog";
import PlayerSearch from "../components/PlayerSearch";

const DEFAULT_ROLE = "pitchers";
const DEFAULT_SEASON = 2025;

export default function Dashboard() {
  const { catalog, manifest, loading, error, search } = useCatalog(
    DEFAULT_ROLE,
    DEFAULT_SEASON,
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p className="mt-2 text-gray-600">Welcome to Doubleday.</p>

      {manifest && (
        <p className="mt-1 text-xs text-gray-400">
          {manifest.counts.players} players &middot; Data through{" "}
          {manifest.coverage.last_game_date_seen}
        </p>
      )}

      <div className="mt-6">
        <PlayerSearch
          catalog={catalog}
          loading={loading}
          error={error}
          search={search}
        />
      </div>
    </div>
  );
}
