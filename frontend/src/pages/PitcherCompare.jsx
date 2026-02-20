import { useState, useMemo } from "react";
import { useParams, useLocation, Link } from "react-router";
import useCatalog from "../hooks/useCatalog";
import usePitchData from "../hooks/usePitchData";
import PlayerSearch from "../components/PlayerSearch";
import CompareMovementChart from "../components/CompareMovementChart";
import CompareStatsTable from "../components/CompareStatsTable";

/**
 * Pitcher comparison page.
 *
 * Displays two pitcher panels side-by-side with independent season selectors,
 * an overlay movement chart, and a side-by-side stats table. Pitcher A comes
 * from the URL param; Pitcher B is selected via typeahead search on the page.
 */
export default function PitcherCompare() {
  const { idA } = useParams();
  const pitcherAId = Number(idA);
  const location = useLocation();
  const initialSeason = location.state?.season || 2025;

  const initialPitcherBId = location.state?.pitcherBId
    ? Number(location.state.pitcherBId)
    : null;
  const initialSeasonB = location.state?.seasonB || initialSeason;

  const [seasonA, setSeasonA] = useState(initialSeason);
  const [seasonB, setSeasonB] = useState(initialSeasonB);
  const [pitcherBId, setPitcherBId] = useState(initialPitcherBId);
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
      return catalogB.players.find((p) => p.id === pitcherBId) || pitcherBPlayer;
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
    <div>
      <Link
        to={`/pitchers/${idA}`}
        className="mb-4 hidden text-sm text-gray-500 hover:text-gray-700 sm:inline-block"
      >
        &larr; Back to Pitcher
      </Link>

      {/* Pitcher panels */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
        {/* Pitcher A panel */}
        <div>
          {catalogALoading && (
            <p className="text-sm text-gray-400">Loading pitcher info...</p>
          )}
          {playerA && (
            <div className="flex items-center gap-3">
              <img
                src={playerA.headshot_url}
                alt=""
                className="h-12 w-12 rounded-full bg-gray-100 object-cover"
                onError={(e) => {
                  e.target.style.display = "none";
                }}
              />
              <div>
                <h2 className="flex items-center gap-1.5 text-base font-bold text-gray-900 sm:text-lg">
                  <span className="inline-block h-3 w-3 shrink-0 rounded-full bg-gray-500" />
                  {playerA.first} {playerA.last}
                </h2>
                <p className="text-xs text-gray-600">
                  {teamA?.abbr || "\u2014"} &middot;{" "}
                  {playerA.pos || "\u2014"}
                </p>
              </div>
            </div>
          )}
          <div className="mt-2 flex gap-2">
            {[2024, 2025].map((s) => (
              <button
                key={s}
                onClick={() => setSeasonA(s)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium sm:px-4 sm:py-2 sm:text-sm ${
                  seasonA === s
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Pitcher B panel */}
        <div>
          {pitcherBId && playerB ? (
            <div>
              <div className="flex items-center gap-3">
                <img
                  src={playerB.headshot_url}
                  alt=""
                  className="h-12 w-12 rounded-full bg-gray-100 object-cover"
                  onError={(e) => {
                    e.target.style.display = "none";
                  }}
                />
                <div>
                  <h2 className="flex items-center gap-1.5 text-base font-bold text-gray-900 sm:text-lg">
                    <span className="inline-block h-3 w-3 shrink-0 rounded-full border-2 border-gray-500 bg-white" />
                    {playerB.first} {playerB.last}
                  </h2>
                  <p className="text-xs text-gray-600">
                    {teamB?.abbr || "\u2014"} &middot;{" "}
                    {playerB.pos || "\u2014"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleChangeB}
                  className="ml-auto rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Change
                </button>
              </div>
              <div className="mt-2 flex gap-2">
                {[2024, 2025].map((s) => (
                  <button
                    key={s}
                    onClick={() => setSeasonB(s)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium sm:px-4 sm:py-2 sm:text-sm ${
                      seasonB === s
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <PlayerSearch
              catalog={catalogB}
              loading={catalogBLoading}
              error={catalogBError}
              search={searchB}
              onSelect={handleSelectB}
            />
          )}
        </div>
      </div>

      {/* Loading / error states */}
      {(pitchALoading || pitchBLoading) && pitcherBId && (
        <p className="mt-6 text-sm text-gray-400">Loading pitch data...</p>
      )}
      {pitchBError && (
        <p className="mt-6 text-sm text-red-600">{pitchBError}</p>
      )}

      {/* Chart and table */}
      {bothReady && playerA && playerB && (
        <div className="mt-3 space-y-3 sm:mt-6 sm:space-y-6">
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
        </div>
      )}

      {/* No data messages */}
      {sortedA && sortedA.length === 0 && (
        <p className="mt-6 text-sm text-gray-500">
          No pitch data for Pitcher A in {seasonA}.
        </p>
      )}
      {pitcherBId && sortedB && sortedB.length === 0 && (
        <p className="mt-6 text-sm text-gray-500">
          No pitch data for Pitcher B in {seasonB}.
        </p>
      )}
    </div>
  );
}
