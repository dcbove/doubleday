"""Unit tests for the bronze load pipeline (doubleday.pipeline.bronze_load.pipeline).

The bronze load downloads a single day's Statcast CSV from Baseball Savant and
uploads it to S3 at a Hive-partitioned path (bronze/season=YYYY/game_date=YYYY-MM-DD/).
It supports skip-if-exists behavior (controlled by force_download) and reports
the number of data rows downloaded.

These tests mock the S3 client (head_object, put_object) and urllib.urlopen to
verify: S3 key construction, skip logic, force download override, row counting,
and error handling for S3 failures.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from doubleday.pipeline.bronze_load.pipeline import (
    LoadResult,
    _object_exists,
    _s3_key,
    download_partition,
)


def _make_s3_mock():
    """Create a MagicMock S3 client with real ClientError on exceptions."""
    s3 = MagicMock()
    s3.exceptions.ClientError = ClientError
    return s3


class TestS3Key:
    """Tests for _s3_key — builds the Hive-partitioned S3 path for a game date."""

    def test_builds_correct_key(self):
        """Builds the expected Hive-style S3 key."""
        key = _s3_key(2024, "2024-03-01")
        assert key == "bronze/season=2024/game_date=2024-03-01/statcast.csv"

    def test_different_season(self):
        """Different season produces correct key."""
        key = _s3_key(2025, "2025-07-15")
        assert key == "bronze/season=2025/game_date=2025-07-15/statcast.csv"


class TestObjectExists:
    """Tests for _object_exists — checks if an S3 key exists via head_object."""

    def test_returns_true_when_exists(self):
        """Returns True when head_object succeeds."""
        s3 = _make_s3_mock()
        assert _object_exists(s3, "bucket", "key") is True
        s3.head_object.assert_called_once_with(Bucket="bucket", Key="key")

    def test_returns_false_on_404(self):
        """Returns False when head_object raises 404."""
        s3 = _make_s3_mock()
        s3.head_object.side_effect = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        assert _object_exists(s3, "bucket", "key") is False

    def test_raises_on_other_error(self):
        """Re-raises non-404 ClientError."""
        s3 = _make_s3_mock()
        s3.head_object.side_effect = ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject")
        with pytest.raises(ClientError):
            _object_exists(s3, "bucket", "key")


class TestDownloadPartition:
    """Tests for download_partition — the main bronze load entry point.

    Verifies the full download flow: check S3 for existing file, optionally
    skip, download CSV from Baseball Savant, upload to S3, and count records.
    """

    @patch("doubleday.pipeline.bronze_load.pipeline._object_exists", return_value=True)
    def test_skip_when_exists_and_not_forced(self, mock_exists):
        """Skips download when file exists and force_download is False."""
        s3 = MagicMock()
        result = download_partition(s3, "bucket", 2024, "2024-03-01")

        assert isinstance(result, LoadResult)
        assert result.skipped is True
        assert result.records_downloaded == 0
        s3.put_object.assert_not_called()

    @patch("doubleday.pipeline.bronze_load.pipeline.urlopen")
    @patch("doubleday.pipeline.bronze_load.pipeline._object_exists", return_value=True)
    def test_force_download_when_exists(self, mock_exists, mock_urlopen):
        """Downloads even when file exists if force_download is True."""
        csv_body = b"col1,col2\nval1,val2\nval3,val4\n"
        mock_resp = MagicMock()
        mock_resp.read.return_value = csv_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        s3 = MagicMock()
        result = download_partition(s3, "bucket", 2024, "2024-03-01", force_download=True)

        assert result.skipped is False
        assert result.records_downloaded == 2
        s3.put_object.assert_called_once()

    @patch("doubleday.pipeline.bronze_load.pipeline.urlopen")
    @patch("doubleday.pipeline.bronze_load.pipeline._object_exists", return_value=False)
    def test_download_when_not_exists(self, mock_exists, mock_urlopen):
        """Downloads when file does not exist."""
        csv_body = b"col1,col2\nval1,val2\n"
        mock_resp = MagicMock()
        mock_resp.read.return_value = csv_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        s3 = MagicMock()
        result = download_partition(s3, "bucket", 2024, "2024-03-01")

        assert result.skipped is False
        assert result.records_downloaded == 1
        s3.put_object.assert_called_once()
        call_kwargs = s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "bucket"
        expected_key = "bronze/season=2024/game_date=2024-03-01/statcast.csv"
        assert call_kwargs["Key"] == expected_key
        assert call_kwargs["Body"] == csv_body

    @patch("doubleday.pipeline.bronze_load.pipeline.urlopen")
    @patch("doubleday.pipeline.bronze_load.pipeline._object_exists", return_value=False)
    def test_records_count_from_csv(self, mock_exists, mock_urlopen):
        """Records count is number of data rows (excluding header)."""
        # 1 header + 5 data rows
        lines = ["h1,h2"] + [f"v{i},v{i}" for i in range(5)]
        csv_body = ("\n".join(lines) + "\n").encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = csv_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        s3 = MagicMock()
        result = download_partition(s3, "bucket", 2024, "2024-03-01")

        assert result.records_downloaded == 5

    @patch("doubleday.pipeline.bronze_load.pipeline.urlopen")
    @patch("doubleday.pipeline.bronze_load.pipeline._object_exists", return_value=False)
    def test_empty_csv_returns_zero_records(self, mock_exists, mock_urlopen):
        """Header-only CSV returns zero records."""
        csv_body = b"col1,col2\n"
        mock_resp = MagicMock()
        mock_resp.read.return_value = csv_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        s3 = MagicMock()
        result = download_partition(s3, "bucket", 2024, "2024-03-01")

        assert result.records_downloaded == 0
