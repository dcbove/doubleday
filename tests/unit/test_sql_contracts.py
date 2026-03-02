"""SQL contract tests — verify every referenced SQL file exists and no SQL file is orphaned."""

import re
from pathlib import Path

from doubleday.pipeline.gold_load.pipeline import STEPS as GOLD_STEPS
from doubleday.pipeline.silver_load.pipeline import STEPS as SILVER_STEPS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
SRC_DIR = PROJECT_ROOT / "src" / "doubleday"

# Gold table names from the Step Function's SetGoldTables pass state.
GOLD_TABLES = [
    "gold_pitches_shape_season",
    "gold_pitch_type_norm_stats",
    "gold_repertoire_shape_neighbors",
    "gold_catalog",
]

# Matches "api/foo.sql" or "pipeline/foo.sql" as a single string literal.
_SQL_REF_PATTERN = re.compile(r"""["']((?:api|pipeline)/[^"']+\.sql)["']""")

# Matches Path(...) / "pipeline" / "foo.sql" style references.
_PATH_JOIN_PATTERN = re.compile(r"""["'](pipeline|api)["']\s*/\s*["']([^"']+\.sql)["']""")


def _all_referenced_sql_files() -> set[str]:
    """Scan all Python source for SQL file references.

    Finds every string literal matching ``api/*.sql`` or ``pipeline/*.sql``
    in ``src/doubleday/``. Gold step templates containing ``{table_name}``
    are expanded with the known gold table names.
    """
    referenced: set[str] = set()

    for py_file in SRC_DIR.rglob("*.py"):
        source = py_file.read_text()

        for match in _SQL_REF_PATTERN.findall(source):
            if "{table_name}" in match:
                for table_name in GOLD_TABLES:
                    referenced.add(match.format(table_name=table_name))
            else:
                referenced.add(match)

        # Path / "pipeline" / "foo.sql" style joins
        for prefix, filename in _PATH_JOIN_PATTERN.findall(source):
            referenced.add(f"{prefix}/{filename}")

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

    def test_no_orphaned_pipeline_sql(self) -> None:
        """Every .sql file in sql/pipeline/ must be referenced by code."""
        referenced = _all_referenced_sql_files()
        pipeline_referenced = {f.split("/", 1)[1] for f in referenced if f.startswith("pipeline/")}
        on_disk = {f.name for f in (SQL_DIR / "pipeline").glob("*.sql")}
        orphaned = on_disk - pipeline_referenced
        assert not orphaned, f"Orphaned SQL files in sql/pipeline/ not referenced by any code: {orphaned}"
