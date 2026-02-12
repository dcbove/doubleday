# Doubleday

Analysis and processing of pitch-by-pitch MLB data sourced from Baseball Savant's Statcast system.

## Setup

```bash
brew install pyenv uv
pyenv install 3.13

git clone <repo-url> doubleday
cd doubleday
make install
```

## Development

```bash
make test          # Run tests
make lint          # Lint with ruff
make format        # Format with black
make typecheck     # Type check with mypy
make check-all     # Run all checks
```

## Data: Bronze Layer

The bronze layer is raw, unmodified Statcast pitch-by-pitch CSV data downloaded from Baseball Savant. All columns are stored as strings. Data is Hive-style partitioned by season and game date for use with Athena and Glue.

### Download

```bash
bash util/download_year.sh <year>
```

One CSV per day across the MLB season (March through November). Baseball Savant caps exports at ~25,000 rows per request; the script warns if any file hits this limit.

### Local layout

```
data/bronze/
└── season=2025/
    ├── game_date=2025-03-01/statcast.csv
    ├── game_date=2025-03-02/statcast.csv
    └── ...
```

### Sync with S3

```bash
# Upload
aws s3 sync data/bronze/ s3://doubleday-<env>-lakehouse/bronze/

# Download
aws s3 sync s3://doubleday-<env>-lakehouse/bronze/ data/bronze/
```

### Query with Athena

The bronze table is available as `doubleday_<env>.bronze_statcast`. Always filter on partition keys for performance:

```sql
SELECT pitch_type, count(*)
FROM doubleday_dev.bronze_statcast
WHERE season = 2025
GROUP BY pitch_type
```