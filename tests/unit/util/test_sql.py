"""Unit tests for doubleday.util.sql — SQL generation utilities."""

from doubleday.util.sql import _escape_value, build_values_insert


class TestEscapeValue:
    """Tests for _escape_value."""

    def test_none_returns_null(self):
        """None values produce SQL NULL."""
        assert _escape_value(None) == "NULL"

    def test_bool_true(self):
        """Boolean True produces lowercase 'true'."""
        assert _escape_value(True) == "true"

    def test_bool_false(self):
        """Boolean False produces lowercase 'false'."""
        assert _escape_value(False) == "false"

    def test_int(self):
        """Integer values pass through as numeric literals."""
        assert _escape_value(42) == "42"

    def test_negative_int(self):
        """Negative integers are preserved."""
        assert _escape_value(-7) == "-7"

    def test_float(self):
        """Float values pass through as numeric literals."""
        assert _escape_value(3.14) == "3.14"

    def test_zero(self):
        """Zero is a numeric literal, not NULL."""
        assert _escape_value(0) == "0"

    def test_simple_string(self):
        """Simple strings are single-quoted."""
        assert _escape_value("hello") == "'hello'"

    def test_string_with_apostrophe(self):
        """Single quotes in strings are doubled for SQL escaping."""
        assert _escape_value("O'Brien") == "'O''Brien'"

    def test_string_with_multiple_apostrophes(self):
        """Multiple apostrophes are each doubled."""
        assert _escape_value("it's a 'test'") == "'it''s a ''test'''"

    def test_empty_string(self):
        """Empty strings produce an empty quoted string, not NULL."""
        assert _escape_value("") == "''"

    def test_accented_characters(self):
        """Accented characters pass through unchanged (UTF-8 native in Athena)."""
        assert _escape_value("Ramírez") == "'Ramírez'"

    def test_unicode_characters(self):
        """Various Unicode characters pass through unchanged."""
        assert _escape_value("José Abréu") == "'José Abréu'"


class TestBuildValuesInsert:
    """Tests for build_values_insert."""

    def test_empty_rows(self):
        """Empty row list returns empty statement list."""
        result = build_values_insert("t", ["a", "b"], [])
        assert result == []

    def test_single_row(self):
        """Single row produces one INSERT statement."""
        rows = [{"name": "Yankees", "id": 147}]
        result = build_values_insert("silver_teams", ["id", "name"], rows)
        assert len(result) == 1
        assert result[0] == ("INSERT INTO silver_teams (id, name)\n" "VALUES\n" "(147, 'Yankees')")

    def test_multiple_rows(self):
        """Multiple rows within batch_size produce one INSERT."""
        rows = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ]
        result = build_values_insert("t", ["id", "name"], rows)
        assert len(result) == 1
        assert "(1, 'A')" in result[0]
        assert "(2, 'B')" in result[0]

    def test_batch_splitting(self):
        """Rows exceeding batch_size are split into multiple INSERTs."""
        rows = [{"id": i, "val": f"row{i}"} for i in range(250)]
        result = build_values_insert("t", ["id", "val"], rows, batch_size=100)
        assert len(result) == 3
        # Count value rows by newlines in the VALUES clause
        assert result[0].count("\n") == 101  # header + VALUES + 100 rows (99 commas)
        assert result[1].count("\n") == 101
        assert result[2].count("\n") == 51  # header + VALUES + 50 rows

    def test_exact_batch_size(self):
        """Exactly batch_size rows produce one INSERT."""
        rows = [{"id": i} for i in range(100)]
        result = build_values_insert("t", ["id"], rows, batch_size=100)
        assert len(result) == 1

    def test_batch_size_plus_one(self):
        """batch_size + 1 rows produce two INSERTs."""
        rows = [{"id": i} for i in range(101)]
        result = build_values_insert("t", ["id"], rows, batch_size=100)
        assert len(result) == 2

    def test_null_handling(self):
        """None values in rows produce NULL in SQL."""
        rows = [{"id": 1, "score": None}]
        result = build_values_insert("t", ["id", "score"], rows)
        assert "(1, NULL)" in result[0]

    def test_boolean_handling(self):
        """Boolean values produce lowercase true/false."""
        rows = [{"id": 1, "active": True}, {"id": 2, "active": False}]
        result = build_values_insert("t", ["id", "active"], rows)
        assert "(1, true)" in result[0]
        assert "(2, false)" in result[0]

    def test_apostrophe_escaping_in_values(self):
        """Apostrophes in string values are properly escaped."""
        rows = [{"id": 1, "name": "O'Brien"}]
        result = build_values_insert("t", ["id", "name"], rows)
        assert "(1, 'O''Brien')" in result[0]

    def test_missing_column_produces_null(self):
        """Row dicts missing a column key produce NULL via dict.get()."""
        rows = [{"id": 1}]
        result = build_values_insert("t", ["id", "name"], rows)
        assert "(1, NULL)" in result[0]

    def test_column_ordering(self):
        """Values follow the column list order, not dict key order."""
        rows = [{"b": "second", "a": "first"}]
        result = build_values_insert("t", ["a", "b"], rows)
        assert "('first', 'second')" in result[0]

    def test_custom_batch_size(self):
        """Custom batch_size is respected."""
        rows = [{"id": i} for i in range(10)]
        result = build_values_insert("t", ["id"], rows, batch_size=3)
        assert len(result) == 4  # 3 + 3 + 3 + 1

    def test_float_values(self):
        """Float values pass through as numeric literals."""
        rows = [{"lat": 40.829, "lng": -73.926}]
        result = build_values_insert("t", ["lat", "lng"], rows)
        assert "(40.829, -73.926)" in result[0]
