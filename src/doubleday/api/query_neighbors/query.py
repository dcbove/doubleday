"""Query neighbors — DynamoDB query and result formatting."""

from dataclasses import dataclass, field

from doubleday.util.dynamodb import query_items


@dataclass
class QueryResult:
    """Result of a shape-neighbors query."""

    pitcher: int
    season: int
    neighbors: list[dict] = field(default_factory=list)


def query_neighbors(
    table,
    pitcher: int,
    season: int,
) -> QueryResult:
    """Query pitcher shape-similarity neighbors from the DynamoDB serving table.

    Args:
        table: Boto3 DynamoDB Table resource.
        pitcher: The pitcher's MLB ID.
        season: The season year.

    Returns:
        QueryResult with pitcher, season, and list of neighbor dicts.
    """
    pk = f"PITCHER#{pitcher}#SEASON#{season}"
    neighbors = query_items(table, pk, sk_prefix="NEIGHBOR#")

    return QueryResult(pitcher=pitcher, season=season, neighbors=neighbors)
