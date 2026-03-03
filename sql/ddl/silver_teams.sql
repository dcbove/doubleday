-- silver_teams: team dimension table from MLB Stats API
-- Rebuilt per season via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS silver_teams (
  team_id        int,
  abbreviation   string,
  team_name      string,
  full_name      string,
  league_id      int,
  league_name    string,
  division_id    int,
  division_name  string,
  venue_id       int,
  active         boolean,

  -- partition column
  season         int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/silver/silver_teams/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
