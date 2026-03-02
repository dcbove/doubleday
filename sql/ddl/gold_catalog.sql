-- gold_catalog: denormalized player catalog for API serving
-- Rebuilt from silver_pitches + silver_players + silver_teams via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS gold_catalog (
  player_id              int,
  first_name             string,
  last_name              string,
  last_norm              string,
  bats                   string,
  throws                 string,
  position               string,
  team_season_id         int,
  team_season_abbr       string,
  team_season_name       string,
  team_current_id        int,
  team_current_abbr      string,
  team_current_name      string,
  headshot_url           string,
  role                   string,

  -- partition column
  season                 int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/gold/gold_catalog/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
