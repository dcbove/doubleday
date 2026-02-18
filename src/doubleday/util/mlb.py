"""MLB Stats API client for player enrichment and team lookups.

Provides functions to fetch player metadata (name, bats/throws, position,
current team) and team metadata (abbreviation, name) from the public MLB
Stats API (statsapi.mlb.com). Used by the catalog build pipeline to enrich
the player ID set extracted from silver_pitches.

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
