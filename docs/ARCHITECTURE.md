# Architecture Decisions

Design rationale for key architectural choices in the Doubleday pipeline. For project overview and data model, see [README.md](../README.md).

## Why partition overwrite (DELETE + INSERT) instead of MERGE

Statcast game data is effectively immutable once finalized. Our ingestion unit is already aligned to a natural partition boundary — `(season, game_date)` for silver, `(season)` for gold — and each load always replaces **every row in the partition** from bronze source. We never partially update a partition (e.g., "update 3 rows out of 4,000") — it's always a full reprocess of the day or season. Given that, MERGE offers no efficiency advantage: it would still read and match every row, only to discover they all need replacing. Meanwhile, MERGE (update matched, insert unmatched) would leave behind rows that disappeared from the source — if Statcast retroactively drops a pitch, MERGE can't detect the absence. DELETE + INSERT is simpler, produces fewer Iceberg commits (2 vs 3+), and guarantees canonical exactly mirrors the source for any reprocessed partition.

## Why Standard over Express Step Functions

Standard Step Functions support executions up to one year and have detailed execution history. This matters for backfills — reprocessing an entire season (180+ game dates) can take well over five minutes, which is the Express maximum. Standard also provides per-step visibility in the console, making debugging straightforward.

## Why a single parameterized gold Lambda

One `gold_load` Lambda accepts a table name parameter and executes the corresponding SQL files (`{table_name}_delete.sql` and `{table_name}_insert.sql`). Adding a new gold table means adding two SQL files and a Step Function entry — no Lambda code changes.

## Why the Step Function is the single entry point

All processing flows through the Step Function. There are no S3 event triggers or independent Lambda invocations in production. This eliminates double-processing, makes the pipeline easy to reason about, and gives a single place to monitor execution status.
