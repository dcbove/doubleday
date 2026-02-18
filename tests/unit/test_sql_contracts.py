"""SQL contract tests — verify every referenced SQL file exists and no SQL file is orphaned."""

from pathlib import Path

import pytest

from doubleday.pipeline.catalog_build.pipeline import SQL_FILES as CATALOG_SQL_FILES
from doubleday.pipeline.gold_load.pipeline import STEPS as GOLD_STEPS
from doubleday.pipeline.silver_load.pipeline import STEPS as SILVER_STEPS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

# Gold table names from the Step Function's SetGoldTables pass state.
GOLD_TABLES = ["gold_pitches_shape_season"]


def _resolve_gold_sql_files() -> list[str]:
    """Expand gold step templates with each known gold table name."""
    files = []
    for table_name in GOLD_TABLES:
        for _step_name, sql_template in GOLD_STEPS:
            files.append(sql_template.format(table_name=table_name))
    return files


def _all_referenced_sql_files() -> set[str]:
    """Collect every SQL filename referenced by pipeline and API code.

    All references include their subdirectory prefix (e.g.
    "pipeline/silver_load_partition_into_staging_table.sql" or
    "api/query_pitches.sql"), matching how they are laid out on disk
    under sql/ and bundled in the Lambda zip under doubleday/sql/.
    """
    referenced: set[str] = set()

    # Silver load STEPS
    for _step_name, sql_file in SILVER_STEPS:
        referenced.add(sql_file)

    # Gold load STEPS (resolved with known table names)
    for sql_file in _resolve_gold_sql_files():
        referenced.add(sql_file)

    # Catalog build SQL files
    for sql_file in CATALOG_SQL_FILES.values():
        referenced.add(sql_file)
    referenced.add("pipeline/catalog_coverage.sql")

    # clear_staging direct reference
    referenced.add("pipeline/silver_clear_partition_from_staging_table.sql")

    # query_pitches API reference
    referenced.add("api/query_pitches.sql")

    return referenced


class TestSqlContracts:
    """Ensure SQL references and SQL files stay in sync."""

    def test_silver_steps_files_exist(self) -> None:
        """Every SQL file in silver_load STEPS must exist."""
        for step_name, sql_file in SILVER_STEPS:
            path = SQL_DIR / sql_file
            assert path.exists(), f"Silver step '{step_name}' references '{sql_file}' but {path} does not exist"

    def test_gold_steps_files_exist(self) -> None:
        """Every resolved gold SQL template must exist."""
        for table_name in GOLD_TABLES:
            for step_name, sql_template in GOLD_STEPS:
                sql_file = sql_template.format(table_name=table_name)
                path = SQL_DIR / sql_file
                assert path.exists(), (
                    f"Gold step '{step_name}' for table '{table_name}' "
                    f"references '{sql_file}' but {path} does not exist"
                )

    def test_clear_staging_file_exists(self) -> None:
        """The clear_staging handler's direct SQL reference must exist."""
        path = SQL_DIR / "pipeline" / "silver_clear_partition_from_staging_table.sql"
        assert path.exists(), f"clear_staging references SQL file but {path} does not exist"

    def test_query_pitches_file_exists(self) -> None:
        """The query_pitches API SQL reference must exist."""
        path = SQL_DIR / "api" / "query_pitches.sql"
        assert path.exists(), f"query_pitches references SQL file but {path} does not exist"

    @pytest.mark.skip(reason="temporary")
    def test_no_orphaned_pipeline_sql(self) -> None:
        """Every .sql file in sql/pipeline/ must be referenced by code."""
        referenced = _all_referenced_sql_files()
        pipeline_referenced = {f.split("/", 1)[1] for f in referenced if f.startswith("pipeline/")}
        on_disk = {f.name for f in (SQL_DIR / "pipeline").glob("*.sql")}
        orphaned = on_disk - pipeline_referenced
        assert not orphaned, f"Orphaned SQL files in sql/pipeline/ not referenced by any code: {orphaned}"

    def test_no_orphaned_api_sql(self) -> None:
        """Every .sql file in sql/api/ must be referenced by code."""
        referenced = _all_referenced_sql_files()
        api_referenced = {f.split("/", 1)[1] for f in referenced if f.startswith("api/")}
        on_disk = {f.name for f in (SQL_DIR / "api").glob("*.sql")}
        orphaned = on_disk - api_referenced
        assert not orphaned, f"Orphaned SQL files in sql/api/ not referenced by any code: {orphaned}"
