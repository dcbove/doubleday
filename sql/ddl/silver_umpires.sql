-- silver_umpires: umpire dimension table from MLB Stats API
-- Rebuilt per season via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS silver_umpires (
  umpire_id    int,
  full_name    string,

  -- partition column
  season       int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/silver/silver_umpires/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
