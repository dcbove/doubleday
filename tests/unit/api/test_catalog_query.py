"""Unit tests for the catalog API query (doubleday.api.catalog.query).

The catalog query reads player catalog data from the DynamoDB serving table
for a given season and role. It queries by partition key and sorts results
alphabetically by (last_name, first_name).

These tests mock the DynamoDB table and verify: correct PK construction
(with role singularization), SK prefix, result sorting, and empty results.
"""

from unittest.mock import MagicMock, patch

from doubleday.api.catalog.query import CatalogResult, get_catalog


class TestGetCatalog:
    """Tests for the get_catalog function."""

    @patch("doubleday.api.catalog.query.query_items")
    def test_returns_catalog_result(self, mock_query):
        """Happy path: DynamoDB returns players, parsed into CatalogResult."""
        mock_query.return_value = [
            {"player_id": 605151, "first_name": "Gerrit", "last_name": "Cole"},
        ]

        result = get_catalog(MagicMock(), 2025, "pitchers")

        assert isinstance(result, CatalogResult)
        assert result.season == 2025
        assert result.role == "pitchers"
        assert len(result.players) == 1
        assert result.players[0]["last_name"] == "Cole"

    @patch("doubleday.api.catalog.query.query_items")
    def test_correct_pk_for_pitchers(self, mock_query):
        """PK uses singular role: 'pitchers' → 'pitcher'."""
        mock_query.return_value = []

        get_catalog(MagicMock(), 2025, "pitchers")

        call_args = mock_query.call_args
        assert call_args.args[1] == "CATALOG#pitcher#SEASON#2025"
        assert call_args.kwargs["sk_prefix"] == "PLAYER#"

    @patch("doubleday.api.catalog.query.query_items")
    def test_correct_pk_for_batters(self, mock_query):
        """PK uses singular role: 'batters' → 'batter'."""
        mock_query.return_value = []

        get_catalog(MagicMock(), 2024, "batters")

        call_args = mock_query.call_args
        assert call_args.args[1] == "CATALOG#batter#SEASON#2024"

    @patch("doubleday.api.catalog.query.query_items")
    def test_sorts_by_last_name_first_name(self, mock_query):
        """Players are sorted alphabetically by (last_name, first_name)."""
        mock_query.return_value = [
            {"player_id": 2, "first_name": "Zack", "last_name": "Wheeler"},
            {"player_id": 3, "first_name": "Aaron", "last_name": "Nola"},
            {"player_id": 1, "first_name": "Gerrit", "last_name": "Cole"},
        ]

        result = get_catalog(MagicMock(), 2025, "pitchers")

        names = [p["last_name"] for p in result.players]
        assert names == ["Cole", "Nola", "Wheeler"]

    @patch("doubleday.api.catalog.query.query_items")
    def test_empty_result(self, mock_query):
        """No players returns CatalogResult with empty list."""
        mock_query.return_value = []

        result = get_catalog(MagicMock(), 2025, "pitchers")

        assert result.players == []
        assert result.season == 2025
