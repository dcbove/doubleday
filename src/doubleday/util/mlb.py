"""MLB Stats API client for player enrichment, team, venue, and game lookups.

Provides functions to fetch player metadata (name, bats/throws, position,
current team), team metadata (abbreviation, name, league, division, venue),
venue metadata (address, coordinates), game metadata (schedule, scores), and
umpire metadata from the public MLB Stats API (statsapi.mlb.com).

Used by the catalog build and dimension load pipelines.

All HTTP calls use urllib.request (no third-party HTTP library) to stay
consistent with the bronze_load pattern and avoid adding dependencies to
the Lambda package.
"""

import json
import unicodedata
from dataclasses import dataclass
from urllib.request import Request, urlopen

from aws_lambda_powertools import Logger

logger = Logger(child=True)

PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people?personIds={ids}"
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
TEAMS_SEASON_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1&season={season}"
VENUE_URL = "https://statsapi.mlb.com/api/v1/venues/{venue_id}?hydrate=location"
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=officials"
HEADSHOT_TEMPLATE = (
    "https://img.mlbstatic.com/mlb-photos/image/upload"
    "/d_people:generic:headshot:67:current.png"
    "/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current"
)
BATCH_SIZE = 200


@dataclass
class PlayerEnrichment:
    """Enrichment data for a single player from the MLB Stats API.

    Attributes:
        player_id: MLBAM player ID (e.g. 605151 for Gerrit Cole).
        first_name: Display first name from the API.
        last_name: Display last name from the API.
        bats: Bat-side code ("L", "R", or "S" for switch).
        throws: Pitch-hand code ("L" or "R").
        position: Primary position abbreviation (e.g. "P", "SS", "OF").
        current_team_id: MLB team ID from the player's currentTeam, or None
            if the player has no active team (e.g. free agent, retired).
        headshot_url: Direct URL to the player's MLB-hosted headshot image.
    """

    player_id: int
    first_name: str
    last_name: str
    bats: str
    throws: str
    position: str
    current_team_id: int | None
    headshot_url: str


@dataclass
class TeamInfo:
    """Team metadata from the MLB Stats API.

    Attributes:
        team_id: Numeric MLB team ID (e.g. 147 for the Yankees).
        abbreviation: Three-letter team abbreviation (e.g. "NYY").
        team_name: Short team name without city (e.g. "Yankees").
    """

    team_id: int
    abbreviation: str
    team_name: str


@dataclass
class TeamDetail:
    """Extended team metadata from the MLB Stats API.

    Attributes:
        team_id: Numeric MLB team ID (e.g. 147 for the Yankees).
        abbreviation: Three-letter team abbreviation (e.g. "NYY").
        team_name: Short team name without city (e.g. "Yankees").
        full_name: Full franchise name (e.g. "New York Yankees").
        league_id: Numeric MLB league ID (e.g. 103 for AL).
        league_name: League display name (e.g. "American League").
        division_id: Numeric MLB division ID (e.g. 201 for AL East).
        division_name: Division display name (e.g. "American League East").
        venue_id: Numeric MLB venue ID for the team's home stadium.
        active: Whether the team is currently active.
    """

    team_id: int
    abbreviation: str
    team_name: str
    full_name: str
    league_id: int | None
    league_name: str
    division_id: int | None
    division_name: str
    venue_id: int | None
    active: bool


@dataclass
class VenueInfo:
    """Venue metadata from the MLB Stats API.

    Attributes:
        venue_id: Numeric MLB venue ID.
        name: Venue display name (e.g. "Yankee Stadium").
        address1: Street address line 1.
        city: City name.
        state: Full state name.
        state_abbrev: Two-letter state abbreviation.
        postal_code: ZIP / postal code.
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        elevation: Elevation in feet.
        country: Country name.
    """

    venue_id: int
    name: str
    address1: str
    city: str
    state: str
    state_abbrev: str
    postal_code: str
    latitude: float | None
    longitude: float | None
    elevation: float | None
    country: str


@dataclass
class GameInfo:
    """Game metadata from the MLB Stats API schedule endpoint.

    Attributes:
        game_pk: Unique game identifier.
        game_type: Game type code (e.g. "R" for regular season).
        season: Season year.
        game_date: ISO datetime string of the game start.
        official_date: Calendar date of the game (YYYY-MM-DD).
        venue_id: Numeric MLB venue ID where the game is played.
        day_night: "day" or "night" indicator.
        away_team_id: Numeric MLB team ID of the away team.
        home_team_id: Numeric MLB team ID of the home team.
        away_score: Away team score (None if game not started).
        home_score: Home team score (None if game not started).
        hp_umpire_id: MLBAM ID of the home plate umpire, or None.
        hp_umpire_name: Full name of the home plate umpire, or empty string.
    """

    game_pk: int
    game_type: str
    season: int
    game_date: str
    official_date: str
    venue_id: int | None
    day_night: str
    away_team_id: int
    home_team_id: int
    away_score: int | None
    home_score: int | None
    hp_umpire_id: int | None
    hp_umpire_name: str


@dataclass
class UmpireInfo:
    """Umpire metadata from the MLB Stats API.

    Attributes:
        umpire_id: MLBAM person ID for the umpire.
        full_name: Display name of the umpire.
    """

    umpire_id: int
    full_name: str


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL and return parsed dict.

    Args:
        url: Fully-formed URL to fetch.

    Returns:
        Parsed JSON response as a dict.
    """
    req = Request(url, headers={"User-Agent": "doubleday-etl/1.0"})  # noqa: S310
    with urlopen(req) as resp:  # noqa: S310
        result: dict = json.loads(resp.read())
        return result


def fetch_teams() -> dict[str, TeamInfo]:
    """Fetch all active MLB teams and return a dict keyed by abbreviation.

    Calls the ``/api/v1/teams?sportId=1`` endpoint, which returns only
    Major League teams. Teams without an abbreviation are skipped.

    Returns:
        Dict mapping team abbreviation (e.g. "NYY") to TeamInfo.
    """
    data = _fetch_json(TEAMS_URL)
    teams: dict[str, TeamInfo] = {}
    for team in data.get("teams", []):
        abbr = team.get("abbreviation", "")
        if abbr:
            teams[abbr] = TeamInfo(
                team_id=team["id"],
                abbreviation=abbr,
                team_name=team.get("teamName", ""),
            )
    return teams


def _fetch_people_batch(player_ids: list[int]) -> list[dict]:
    """Fetch a single batch of player data from the MLB Stats API.

    Args:
        player_ids: List of MLBAM player IDs (max BATCH_SIZE).

    Returns:
        List of player dicts from the API response.
    """
    ids_str = ",".join(str(pid) for pid in player_ids)
    url = PEOPLE_URL.format(ids=ids_str)
    data = _fetch_json(url)
    result: list[dict] = data.get("people", [])
    return result


def _parse_player(person: dict) -> PlayerEnrichment:
    """Parse a single player dict from the MLB API into a PlayerEnrichment.

    Missing optional fields default to empty strings (names, codes) or None
    (current_team_id). The headshot URL is constructed from the MLBAM player
    ID rather than read from the API response.

    Args:
        person: Player dict from the MLB Stats API people endpoint.

    Returns:
        PlayerEnrichment dataclass with extracted fields.
    """
    player_id = person["id"]
    current_team = person.get("currentTeam", {})
    position = person.get("primaryPosition", {})
    return PlayerEnrichment(
        player_id=player_id,
        first_name=person.get("firstName", ""),
        last_name=person.get("lastName", ""),
        bats=person.get("batSide", {}).get("code", ""),
        throws=person.get("pitchHand", {}).get("code", ""),
        position=position.get("abbreviation", ""),
        current_team_id=current_team.get("id"),
        headshot_url=HEADSHOT_TEMPLATE.format(player_id=player_id),
    )


def fetch_players(player_ids: list[int]) -> dict[int, PlayerEnrichment]:
    """Fetch player enrichment data in batches from the MLB Stats API.

    Splits the input into batches of BATCH_SIZE (200) IDs per HTTP request.
    Each batch is an independent call to the ``/api/v1/people`` endpoint.
    If a batch fails (network error, API error), it is logged and skipped —
    the remaining batches still proceed and their results are returned.

    This partial-failure tolerance supports the catalog build's last-known-good
    semantics: callers merge API results with a cache so missing players
    retain their previous enrichment rather than being blanked.

    Args:
        player_ids: List of MLBAM player IDs to enrich.

    Returns:
        Dict mapping player ID to PlayerEnrichment for successfully fetched
        players. May be smaller than the input list if batches failed.
    """
    if not player_ids:
        return {}

    result: dict[int, PlayerEnrichment] = {}
    for i in range(0, len(player_ids), BATCH_SIZE):
        batch = player_ids[i : i + BATCH_SIZE]
        try:
            people = _fetch_people_batch(batch)
            for person in people:
                enrichment = _parse_player(person)
                result[enrichment.player_id] = enrichment
        except Exception:
            logger.warning(
                "Batch fetch failed, skipping batch",
                extra={"batch_start": i, "batch_size": len(batch)},
            )
    return result


def fetch_teams_for_season(season: int) -> list[TeamDetail]:
    """Fetch all MLB teams for a given season with extended metadata.

    Calls the ``/api/v1/teams?sportId=1&season={season}`` endpoint. Unlike
    ``fetch_teams`` which returns a dict keyed by abbreviation with minimal
    fields, this returns a list of ``TeamDetail`` with league, division, and
    venue information for use as a dimension table.

    Args:
        season: The season year (e.g. 2025).

    Returns:
        List of TeamDetail for all teams in the response.
    """
    url = TEAMS_SEASON_URL.format(season=season)
    data = _fetch_json(url)
    teams: list[TeamDetail] = []
    for team in data.get("teams", []):
        league = team.get("league", {})
        division = team.get("division", {})
        venue = team.get("venue", {})
        teams.append(
            TeamDetail(
                team_id=team["id"],
                abbreviation=team.get("abbreviation", ""),
                team_name=team.get("teamName", ""),
                full_name=team.get("name", ""),
                league_id=league.get("id"),
                league_name=league.get("name", ""),
                division_id=division.get("id"),
                division_name=division.get("name", ""),
                venue_id=venue.get("id"),
                active=team.get("active", False),
            )
        )
    return teams


def fetch_venues(venue_ids: list[int]) -> list[VenueInfo]:
    """Fetch venue metadata for a list of venue IDs.

    Calls the ``/api/v1/venues/{venue_id}?hydrate=location`` endpoint once
    per venue. Only ~30 MLB stadiums exist so the total call count is small.
    Venues that fail to fetch are logged and skipped.

    Args:
        venue_ids: List of MLB venue IDs to fetch.

    Returns:
        List of VenueInfo for successfully fetched venues.
    """
    venues: list[VenueInfo] = []
    for venue_id in venue_ids:
        try:
            url = VENUE_URL.format(venue_id=venue_id)
            data = _fetch_json(url)
            for venue in data.get("venues", []):
                location = venue.get("location", {})
                coords = location.get("defaultCoordinates", {})
                venues.append(
                    VenueInfo(
                        venue_id=venue["id"],
                        name=venue.get("name", ""),
                        address1=location.get("address1", ""),
                        city=location.get("city", ""),
                        state=location.get("state", ""),
                        state_abbrev=location.get("stateAbbrev", ""),
                        postal_code=location.get("postalCode", ""),
                        latitude=coords.get("latitude"),
                        longitude=coords.get("longitude"),
                        elevation=location.get("elevation"),
                        country=location.get("country", ""),
                    )
                )
        except Exception:
            logger.warning(
                "Failed to fetch venue, skipping",
                extra={"venue_id": venue_id},
            )
    return venues


def _extract_hp_umpire(game: dict) -> tuple[int | None, str]:
    """Extract the home plate umpire from a game's officials list.

    Args:
        game: Game dict from the schedule API response.

    Returns:
        Tuple of (umpire_id, umpire_full_name). Returns (None, "") if
        no home plate umpire is found.
    """
    for official in game.get("officials", []):
        if official.get("officialType") == "Home Plate":
            person = official.get("official", {})
            return person.get("id"), person.get("fullName", "")
    return None, ""


def fetch_schedule(date: str) -> list[GameInfo]:
    """Fetch the MLB schedule for a given date with umpire data.

    Calls the ``/api/v1/schedule?sportId=1&date={date}&hydrate=officials``
    endpoint. Parses each game's metadata including the home plate umpire
    from the officials list.

    Args:
        date: Game date in YYYY-MM-DD format.

    Returns:
        List of GameInfo for all games on the given date.
    """
    url = SCHEDULE_URL.format(date=date)
    data = _fetch_json(url)
    games: list[GameInfo] = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            hp_umpire_id, hp_umpire_name = _extract_hp_umpire(game)
            teams = game.get("teams", {})
            venue = game.get("venue", {})
            games.append(
                GameInfo(
                    game_pk=game["gamePk"],
                    game_type=game.get("gameType", ""),
                    season=int(game.get("season", 0)),
                    game_date=game.get("gameDate", ""),
                    official_date=game.get("officialDate", ""),
                    venue_id=venue.get("id"),
                    day_night=game.get("dayNight", ""),
                    away_team_id=teams.get("away", {}).get("team", {}).get("id", 0),
                    home_team_id=teams.get("home", {}).get("team", {}).get("id", 0),
                    away_score=teams.get("away", {}).get("score"),
                    home_score=teams.get("home", {}).get("score"),
                    hp_umpire_id=hp_umpire_id,
                    hp_umpire_name=hp_umpire_name,
                )
            )
    return games


def fetch_umpires(umpire_ids: list[int]) -> dict[int, UmpireInfo]:
    """Fetch umpire metadata in batches from the MLB Stats API.

    Reuses the ``_fetch_people_batch`` helper (same ``/api/v1/people``
    endpoint and batch pattern used by ``fetch_players``). Each person
    record is parsed into an ``UmpireInfo`` with just ID and full name.

    If a batch fails, it is logged and skipped — remaining batches still
    proceed.

    Args:
        umpire_ids: List of MLBAM person IDs for umpires.

    Returns:
        Dict mapping umpire ID to UmpireInfo for successfully fetched
        umpires.
    """
    if not umpire_ids:
        return {}

    result: dict[int, UmpireInfo] = {}
    for i in range(0, len(umpire_ids), BATCH_SIZE):
        batch = umpire_ids[i : i + BATCH_SIZE]
        try:
            people = _fetch_people_batch(batch)
            for person in people:
                umpire_id = person["id"]
                result[umpire_id] = UmpireInfo(
                    umpire_id=umpire_id,
                    full_name=person.get("fullName", ""),
                )
        except Exception:
            logger.warning(
                "Umpire batch fetch failed, skipping batch",
                extra={"batch_start": i, "batch_size": len(batch)},
            )
    return result


def normalize_name(name: str) -> str:
    """Normalize a name for browser-side prefix search matching.

    Produces the ``last_norm`` field in catalog.json. The SPA normalizes
    the user's search query with the same rules, then filters players
    whose ``last_norm`` starts with the normalized query.

    Steps: NFKD decomposition → strip combining marks (accents) →
    lowercase → remove non-alphanumeric characters.

    Examples:
        >>> normalize_name("Ramírez")
        'ramirez'
        >>> normalize_name("O'Brien")
        'obrien'

    Args:
        name: Raw name string to normalize.

    Returns:
        Normalized string suitable for prefix matching.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c for c in stripped.lower() if c.isalnum())
