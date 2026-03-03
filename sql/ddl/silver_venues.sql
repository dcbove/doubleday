-- silver_venues: venue dimension table from MLB Stats API
-- Rebuilt per season via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS silver_venues (
  venue_id       int,
  name           string,
  address1       string,
  city           string,
  state          string,
  state_abbrev   string,
  postal_code    string,
  latitude       double,
  longitude      double,
  elevation      double,
  country        string,

  -- partition column
  season         int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/silver/silver_venues/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
