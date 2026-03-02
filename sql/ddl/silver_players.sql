-- silver_players: player dimension table from MLB Stats API
-- Rebuilt per season via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS silver_players (
  player_id        int,
  first_name       string,
  last_name        string,
  last_norm        string,
  bats             string,
  throws           string,
  position         string,
  current_team_id  int,
  headshot_url     string,

  -- partition column
  season           int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/silver/silver_players/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
