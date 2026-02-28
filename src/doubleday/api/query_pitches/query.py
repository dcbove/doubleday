"""Query pitches — DynamoDB query and result formatting."""

from dataclasses import dataclass, field

from doubleday.util.dynamodb import query_items


@dataclass
class QueryResult:
    """Result of a pitch-shape query."""

    pitcher: int
    season: int
    pitches: list[dict] = field(default_factory=list)


def query_pitches(
    table,
    pitcher: int,
    season: int,
    pitch_type: str | None = None,
) -> QueryResult:
    """Query pitcher pitch-shape stats from the DynamoDB serving table.

    Args:
        table: Boto3 DynamoDB Table resource.
        pitcher: The pitcher's MLB ID.
        season: The season year.
        pitch_type: Optional pitch type filter (e.g. ``'FF'``, ``'SL'``).

    Returns:
        QueryResult with pitcher, season, and list of pitch-shape dicts.
    """
    pk = f"PITCHER#{pitcher}#SEASON#{season}"

    if pitch_type is not None:
        pitches = query_items(table, pk, sk_prefix="PITCH#", sk_exact=f"PITCH#{pitch_type}")
    else:
        pitches = query_items(table, pk, sk_prefix="PITCH#")

    return QueryResult(pitcher=pitcher, season=season, pitches=pitches)
