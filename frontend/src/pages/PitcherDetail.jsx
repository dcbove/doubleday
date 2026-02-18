import { useState, useMemo } from "react";
import { useParams, Link } from "react-router";
import useCatalog from "../hooks/useCatalog";
import usePitchData from "../hooks/usePitchData";
import PitchMovementChart from "../components/PitchMovementChart";
import PitchStatsTable from "../components/PitchStatsTable";

/**
 * Pitcher detail page showing profile info and an interactive pitch movement chart.
 *
 * Reads the pitcher ID from the URL, resolves name and team from the catalog,
 * fetches pitch aggregation data from the API, and renders a scatter plot of
 * pitch movement with a hoverable stat panel.
 */
export default function PitcherDetail() {
  const { id } = useParams();
  const pitcherId = Number(id);
  const [season, setSeason] = useState(2024);
  const [hoveredPitchType, setHoveredPitchType] = useState(null);

  const { catalog, loading: catalogLoading } = useCatalog("pitchers", season);
  const { pitches, loading: pitchLoading, error: pitchError } = usePitchData(
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
    <div>
      <Link
        to="/dashboard"
        className="mb-4 hidden text-sm text-gray-500 hover:text-gray-700 sm:inline-block"
      >
        &larr; Back to Dashboard
      </Link>

      {/* Pitcher header */}
      {catalogLoading && (
        <p className="text-sm text-gray-400">Loading pitcher info...</p>
      )}
      {!catalogLoading && !player && (
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Pitcher not found
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            No pitcher with ID {pitcherId} in the {season} catalog.
          </p>
        </div>
      )}
      {player && (
        <header className="flex items-center gap-3 sm:gap-4">
          <img
            src={player.headshot_url}
            alt=""
            className="h-12 w-12 rounded-full bg-gray-100 object-cover sm:h-20 sm:w-20"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
          <div>
            <h1 className="text-lg font-bold text-gray-900 sm:text-2xl">
              {player.first} {player.last}
            </h1>
            <p className="text-xs text-gray-600 sm:text-sm">
              {team?.abbr || "\u2014"} &middot; {player.pos || "\u2014"}{" "}
              &middot; B/T: {player.bats}/{player.throws}
            </p>
          </div>
        </header>
      )}

      {/* Season toggle */}
      <div className="mt-2 flex gap-2 sm:mt-4">
        {[2024, 2025].map((s) => (
          <button
            key={s}
            onClick={() => setSeason(s)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium sm:px-4 sm:py-2 sm:text-sm ${
              season === s
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Pitch data */}
      {pitchLoading && (
        <p className="mt-6 text-sm text-gray-400">Loading pitch data...</p>
      )}
      {pitchError && (
        <p className="mt-6 text-sm text-red-600">{pitchError}</p>
      )}
      {sortedPitches && sortedPitches.length === 0 && (
        <p className="mt-6 text-sm text-gray-500">
          No pitch data available for {season}.
        </p>
      )}

      {sortedPitches && sortedPitches.length > 0 && (
        <div className="mt-3 space-y-3 sm:mt-6 sm:space-y-6">
          <PitchMovementChart
            pitches={sortedPitches}
            hoveredPitchType={hoveredPitchType}
            onHover={setHoveredPitchType}
          />
          <PitchStatsTable
            pitches={sortedPitches}
            hoveredPitchType={hoveredPitchType}
            onHover={setHoveredPitchType}
          />
        </div>
      )}
    </div>
  );
}
