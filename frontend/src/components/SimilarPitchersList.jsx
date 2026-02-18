import { useMemo } from "react";
import { Link } from "react-router";

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
    <div className="max-h-[200px] overflow-y-auto rounded-lg border border-gray-200 sm:max-h-none sm:h-full">
      <ul className="divide-y divide-gray-100">
        {rows.map((row) => (
          <li key={`${row.neighbor_pitcher}-${row.neighbor_season}`}>
            <Link
              to={`/pitchers/${sourcePitcherId}/compare`}
              state={{
                season: sourceSeason,
                pitcherBId: row.neighbor_pitcher,
                seasonB: row.neighbor_season,
              }}
              className="flex items-center gap-1.5 px-2 py-1 hover:bg-gray-50 sm:gap-2 sm:px-3 sm:py-1.5"
            >
              {/* Rank */}
              <span className="w-4 shrink-0 text-center text-[9px] font-semibold text-gray-400 sm:text-[11px]">
                {row.rank}
              </span>

              {/* Headshot */}
              {row.player ? (
                <img
                  src={row.player.headshot_url}
                  alt=""
                  className="h-5 w-5 shrink-0 rounded-full bg-gray-100 object-cover sm:h-6 sm:w-6"
                  onError={(e) => {
                    e.target.style.display = "none";
                  }}
                />
              ) : (
                <span className="h-5 w-5 shrink-0 rounded-full bg-gray-200 sm:h-6 sm:w-6" />
              )}

              {/* Name + team */}
              <div className="min-w-0 flex-1">
                <p className="truncate text-[10px] font-medium text-gray-900 sm:text-xs">
                  {row.player
                    ? `${row.player.first} ${row.player.last}`
                    : `Pitcher #${row.neighbor_pitcher}`}
                </p>
                <p className="truncate text-[9px] leading-tight text-gray-500 sm:text-[11px]">
                  {row.team?.abbr || "\u2014"} &middot; {row.neighbor_season}
                </p>
              </div>

              {/* Similarity score */}
              <span className="shrink-0 text-[9px] text-gray-500 sm:text-[11px]">
                {(row.similarity_score * 100).toFixed(1)}%
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
