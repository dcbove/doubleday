"""Catalog query — read player catalog from DynamoDB serving table."""

from dataclasses import dataclass, field

from doubleday.util.dynamodb import query_items


@dataclass
class CatalogResult:
    """Result of a catalog query."""

    season: int
    role: str
    players: list[dict] = field(default_factory=list)


def get_catalog(table, season: int, role: str) -> CatalogResult:
    """Query the player catalog from the DynamoDB serving table.

    Args:
        table: Boto3 DynamoDB Table resource.
        season: The season year.
        role: Player role (``"pitchers"`` or ``"batters"``).

    Returns:
        CatalogResult with season, role, and list of player dicts sorted
        by (last_name, first_name).
    """
    role_singular = role.rstrip("s")
    pk = f"CATALOG#{role_singular}#SEASON#{season}"
    players = query_items(table, pk, sk_prefix="PLAYER#")
    players.sort(key=lambda p: (p.get("last_name", ""), p.get("first_name", "")))
    return CatalogResult(season=season, role=role, players=players)
