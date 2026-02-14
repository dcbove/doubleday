"""Lambda handler for validate_input — validate dates and normalize input."""

import uuid
from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Validate game_date years match season and default force_download.

    Args:
        event: Step Function input with season, game_dates, and optional
            force_download.
        context: Lambda context (unused).

    Returns:
        Normalized input with force_download defaulted to False if missing.

    Raises:
        ValueError: If any game_date year does not match season.
    """
    season = event["season"]
    game_dates = event["game_dates"]
    force_download = event.get("force_download", False)

    for game_date in game_dates:
        year = int(game_date.split("-")[0])
        if year != season:
            raise ValueError(
                f"game_date {game_date} year ({year}) does not match "
                f"season ({season})"
            )

    return {
        "season": season,
        "game_dates": game_dates,
        "force_download": force_download,
        "batch_id": str(uuid.uuid4()),
    }
