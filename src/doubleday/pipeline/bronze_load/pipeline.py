"""Bronze load pipeline — download from Baseball Savant and upload to S3."""

from dataclasses import dataclass
from urllib.request import Request, urlopen

from aws_lambda_powertools import Logger

logger = Logger(child=True)

SAVANT_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv"
    "?all=true&type=details"
    "&game_date_gt={game_date}&game_date_lt={game_date}"
)


@dataclass
class LoadResult:
    """Result of a bronze load partition run."""

    records_downloaded: int
    skipped: bool


def _s3_key(season: int, game_date: str) -> str:
    """Build the S3 key for a bronze partition.

    Args:
        season: MLB season year.
        game_date: Date string in YYYY-MM-DD format.

    Returns:
        S3 object key for the partition CSV.
    """
    return f"bronze/season={season}/game_date={game_date}/statcast.csv"


def _object_exists(s3_client, bucket: str, key: str) -> bool:
    """Check if an S3 object exists using head_object.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        True if the object exists, False otherwise.
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except s3_client.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise
    return True


def download_partition(
    s3_client,
    bucket: str,
    season: int,
    game_date: str,
    force_download: bool = False,
) -> LoadResult:
    """Download a single game date from Baseball Savant to S3.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        season: MLB season year.
        game_date: Date string in YYYY-MM-DD format.
        force_download: If True, download even if the file already exists.

    Returns:
        LoadResult with record count and whether the download was skipped.
    """
    key = _s3_key(season, game_date)

    if not force_download and _object_exists(s3_client, bucket, key):
        logger.info(
            "Partition already exists, skipping download",
            extra={"s3_key": key},
        )
        return LoadResult(records_downloaded=0, skipped=True)

    url = SAVANT_URL.format(game_date=game_date)
    logger.info("Downloading from Baseball Savant", extra={"url": url})
    req = Request(url, headers={"User-Agent": "doubleday-etl/1.0"})
    with urlopen(req) as resp:  # noqa: S310
        body = resp.read()

    s3_client.put_object(Bucket=bucket, Key=key, Body=body)

    # Count data rows (subtract 1 for the header)
    lines = body.decode("utf-8").splitlines()
    records = max(len(lines) - 1, 0)
    logger.info("Uploaded partition to S3", extra={"s3_key": key, "records": records})

    return LoadResult(records_downloaded=records, skipped=False)
