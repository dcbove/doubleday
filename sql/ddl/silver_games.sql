-- silver_games: game dimension table from MLB Stats API schedule endpoint
-- Incrementally loaded per game_date within a season
CREATE TABLE IF NOT EXISTS silver_games (
  game_pk          bigint,
  game_type        string,
  game_date        string,
  official_date    string,
  venue_id         int,
  day_night        string,
  away_team_id     int,
  home_team_id     int,
  away_score       int,
  home_score       int,
  hp_umpire_id     int,
  hp_umpire_name   string,

  -- partition column
  season           int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/silver/silver_games/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
