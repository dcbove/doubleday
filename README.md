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

The bronze layer is raw Statcast pitch-by-pitch data downloaded directly from Baseball Savant. The download script fetches one CSV per day across the MLB season (March through November).

```bash
bash util/download_year.sh <year>
```

Files are saved to `data/bronze/statcast_<year>/` with one file per day:

```
data/bronze/statcast_2025/
├── statcast_2025-03-01.csv
├── statcast_2025-03-02.csv
├── statcast_2025-03-03.csv
└── ...
```

Baseball Savant caps CSV exports at ~25,000 rows. The script warns if any daily file hits this limit.

Sync local bronze data up to S3:

```bash
aws s3 sync data/bronze/ s3://doubleday-<env>-lakehouse/bronze/
```

Pull bronze data down from S3:

```bash
aws s3 sync s3://doubleday-<env>-lakehouse/bronze/ data/bronze/
```