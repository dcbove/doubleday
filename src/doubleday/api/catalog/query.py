"""Catalog manifest query — read pre-built manifest from S3."""

import json
from dataclasses import dataclass

from botocore.exceptions import ClientError


@dataclass
class ManifestResult:
    """Result of a catalog manifest lookup."""

    manifest: dict


def get_manifest(s3, bucket: str, season: int, role: str) -> ManifestResult:
    """Read a catalog manifest from S3.

    Args:
        s3: Boto3 S3 client.
        bucket: Frontend S3 bucket name.
        season: The season year.
        role: Player role (``"pitchers"`` or ``"batters"``).

    Returns:
        ManifestResult containing the parsed manifest dict.

    Raises:
        FileNotFoundError: If the manifest does not exist in S3.
    """
    key = f"static/catalogs/{role}/season={season}/manifest.json"
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            raise FileNotFoundError(f"No manifest at s3://{bucket}/{key}") from exc
        raise
    body = response["Body"].read().decode("utf-8")
    return ManifestResult(manifest=json.loads(body))
