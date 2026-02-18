import { Link } from "react-router";

/**
 * Single player result row in the typeahead dropdown.
 *
 * When `onSelect` is provided, renders a button that calls `onSelect(player)`
 * instead of navigating via Link. Same visual layout either way.
 *
 * @param {{ player: object, teams: object, onSelect?: function }} props
 */
export default function PlayerResult({ player, teams, onSelect }) {
  const team = teams[String(player.team_season_id)] || {};

  const inner = (
    <>
      <img
        src={player.headshot_url}
        alt=""
        className="h-10 w-10 rounded-full bg-gray-100 object-cover"
        loading="lazy"
        onError={(e) => {
          e.target.style.display = "none";
        }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900">
          {player.first} {player.last}
        </p>
        <p className="text-xs text-gray-500">
          {team.abbr || "\u2014"} &middot; {player.pos || "\u2014"} &middot;{" "}
          {player.bats}/{player.throws}
        </p>
      </div>
    </>
  );

  if (onSelect) {
    return (
      <button
        type="button"
        onClick={() => onSelect(player)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-gray-50"
      >
        {inner}
      </button>
    );
  }

  return (
    <Link
      to={`/pitchers/${player.id}`}
      className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50"
    >
      {inner}
    </Link>
  );
}
