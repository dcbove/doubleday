"""Unit tests for the catalog API query (doubleday.api.catalog.query).

The catalog query module reads a pre-built manifest.json from S3 for a given
season and player role. No Athena queries are involved — just an S3 GetObject.

These tests mock the S3 client and verify: correct S3 key construction,
JSON parsing into ManifestResult, and NoSuchKey → FileNotFoundError mapping.
"""

import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from doubleday.api.catalog.query import ManifestResult, get_manifest


class TestGetManifest:
    """Tests for the get_manifest function."""

    def test_returns_manifest_result(self):
        """Happy path: S3 returns manifest JSON, parsed into ManifestResult."""
        manifest_data = {
            "season": 2024,
            "role": "pitchers",
            "blob_key": "static/catalogs/pitchers/season=2024/catalog.json",
            "etag": "abc123",
        }
        s3 = MagicMock()
        s3.get_object.return_value = {
            "Body": BytesIO(json.dumps(manifest_data).encode("utf-8")),
        }

        result = get_manifest(s3, "my-bucket", 2024, "pitchers")

        assert isinstance(result, ManifestResult)
        assert result.manifest == manifest_data

    def test_correct_s3_key(self):
        """S3 key is constructed from role and season."""
        s3 = MagicMock()
        s3.get_object.return_value = {
            "Body": BytesIO(b"{}"),
        }

        get_manifest(s3, "my-bucket", 2023, "batters")

        s3.get_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="static/catalogs/batters/season=2023/manifest.json",
        )

    def test_no_such_key_raises_file_not_found(self):
        """NoSuchKey ClientError is mapped to FileNotFoundError."""
        s3 = MagicMock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        with pytest.raises(FileNotFoundError, match="No manifest"):
            get_manifest(s3, "my-bucket", 2024, "pitchers")

    def test_other_client_error_propagates(self):
        """Non-NoSuchKey ClientError is re-raised as-is."""
        s3 = MagicMock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "GetObject",
        )

        with pytest.raises(ClientError, match="Forbidden"):
            get_manifest(s3, "my-bucket", 2024, "pitchers")
