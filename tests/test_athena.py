"""Unit tests for doubleday.util.athena."""

from unittest.mock import MagicMock, call, patch

import pytest

from doubleday.util.athena import get_query_row_count, run_query


class TestRunQuery:
    """Tests for run_query."""

    def test_returns_execution_id_on_immediate_success(self):
        """Query succeeds on the first poll."""
        client = MagicMock()
        client.start_query_execution.return_value = {"QueryExecutionId": "abc-123"}
        client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }

        result = run_query(client, "SELECT 1", "my_db", "my-bucket")

        assert result == "abc-123"
        client.start_query_execution.assert_called_once_with(
            QueryString="SELECT 1",
            QueryExecutionContext={"Database": "my_db"},
            ResultConfiguration={"OutputLocation": "s3://my-bucket/"},
        )

    @patch("doubleday.util.athena.time.sleep")
    def test_polls_until_succeeded(self, mock_sleep):
        """Query transitions through RUNNING before succeeding."""
        client = MagicMock()
        client.start_query_execution.return_value = {"QueryExecutionId": "abc-123"}
        client.get_query_execution.side_effect = [
            {"QueryExecution": {"Status": {"State": "RUNNING"}}},
            {"QueryExecution": {"Status": {"State": "RUNNING"}}},
            {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}},
        ]

        result = run_query(client, "SELECT 1", "my_db", "my-bucket")

        assert result == "abc-123"
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)

    def test_raises_on_failed_query(self):
        """Query that fails raises RuntimeError with the reason."""
        client = MagicMock()
        client.start_query_execution.return_value = {"QueryExecutionId": "abc-123"}
        client.get_query_execution.return_value = {
            "QueryExecution": {
                "Status": {
                    "State": "FAILED",
                    "StateChangeReason": "Syntax error",
                }
            }
        }

        with pytest.raises(RuntimeError, match="Query FAILED: Syntax error"):
            run_query(client, "BAD SQL", "my_db", "my-bucket")

    def test_raises_on_cancelled_query(self):
        """Cancelled query raises RuntimeError."""
        client = MagicMock()
        client.start_query_execution.return_value = {"QueryExecutionId": "abc-123"}
        client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "CANCELLED"}}
        }

        with pytest.raises(RuntimeError, match="Query CANCELLED: Unknown"):
            run_query(client, "SELECT 1", "my_db", "my-bucket")


class TestGetQueryRowCount:
    """Tests for get_query_row_count."""

    def test_returns_update_count_when_present(self):
        """MERGE results use UpdateCount."""
        client = MagicMock()
        client.get_query_results.return_value = {
            "UpdateCount": 42,
            "ResultSet": {"Rows": []},
        }

        assert get_query_row_count(client, "abc-123") == 42

    def test_returns_row_value_for_insert(self):
        """INSERT results use ResultSet.Rows[1]."""
        client = MagicMock()
        client.get_query_results.return_value = {
            "UpdateCount": 0,
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "count"}]},
                    {"Data": [{"VarCharValue": "150"}]},
                ]
            },
        }

        assert get_query_row_count(client, "abc-123") == 150

    def test_returns_zero_when_no_rows(self):
        """Empty result set returns 0."""
        client = MagicMock()
        client.get_query_results.return_value = {
            "ResultSet": {"Rows": [{"Data": [{"VarCharValue": "count"}]}]},
        }

        assert get_query_row_count(client, "abc-123") == 0
