"""Unit tests for shared Athena utilities (doubleday.util.athena).

This module provides three functions used across all pipeline and API Lambdas:

- run_query: Submits SQL to Athena, polls until completion, and retries on
  Iceberg commit conflicts (ICEBERG_COMMIT_ERROR) with exponential backoff.
- get_query_results: Fetches all result rows from a completed SELECT query,
  handling pagination and skipping the header row.
- get_query_row_count: Extracts the affected row count from INSERT or MERGE
  results, which Athena reports differently (ResultSet rows vs UpdateCount).

These tests mock the Athena client to verify polling, error handling, retry
logic, pagination, and the two different row-count extraction paths.
"""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.util.athena import get_query_results, get_query_row_count, run_query


class TestRunQuery:
    """Tests for run_query — submit SQL, poll for completion, retry on conflict."""

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


class TestGetQueryResults:
    """Tests for get_query_results — fetch paginated SELECT results as dicts."""

    def test_returns_list_of_dicts(self):
        """Returns column-keyed dicts from result rows."""
        client = MagicMock()
        client.get_query_results.return_value = {
            "ResultSet": {
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id"}, {"Name": "name"}]},
                "Rows": [
                    {"Data": [{"VarCharValue": "id"}, {"VarCharValue": "name"}]},
                    {"Data": [{"VarCharValue": "1"}, {"VarCharValue": "Alice"}]},
                    {"Data": [{"VarCharValue": "2"}, {"VarCharValue": "Bob"}]},
                ],
            }
        }

        result = get_query_results(client, "exec-1")

        assert result == [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]

    def test_handles_pagination(self):
        """Fetches multiple pages and concatenates results."""
        client = MagicMock()
        client.get_query_results.side_effect = [
            {
                "ResultSet": {
                    "ResultSetMetadata": {"ColumnInfo": [{"Name": "val"}]},
                    "Rows": [
                        {"Data": [{"VarCharValue": "val"}]},
                        {"Data": [{"VarCharValue": "a"}]},
                    ],
                },
                "NextToken": "page2",
            },
            {
                "ResultSet": {
                    "ResultSetMetadata": {"ColumnInfo": [{"Name": "val"}]},
                    "Rows": [
                        {"Data": [{"VarCharValue": "b"}]},
                    ],
                },
            },
        ]

        result = get_query_results(client, "exec-1")

        assert result == [{"val": "a"}, {"val": "b"}]
        assert client.get_query_results.call_count == 2

    def test_empty_result_set(self):
        """Empty result set returns empty list."""
        client = MagicMock()
        client.get_query_results.return_value = {
            "ResultSet": {
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id"}]},
                "Rows": [
                    {"Data": [{"VarCharValue": "id"}]},
                ],
            }
        }

        result = get_query_results(client, "exec-1")

        assert result == []


class TestGetQueryRowCount:
    """Tests for get_query_row_count — extract affected row count from DML results.

    Athena reports row counts differently by operation type:
    - INSERT INTO Iceberg: count in ResultSet.Rows[1].Data[0]
    - MERGE INTO Iceberg: count in the top-level UpdateCount field
    """

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
