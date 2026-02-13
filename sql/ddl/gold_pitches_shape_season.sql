-- gold_pitches_shape_season: per-pitcher, per-pitch-type season aggregations
-- Rebuilt from silver_pitches via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS gold_pitches_shape_season (
  pitcher                bigint,
  pitch_type             string,
  avg_horz_break         double,
  avg_ivb                double,
  stddev_horz_break      double,
  stddev_ivb             double,
  p10_horz_break         double,
  p90_horz_break         double,
  p10_ivb                double,
  p90_ivb                double,
  avg_velocity           double,
  p10_velocity           double,
  p90_velocity           double,
  avg_adj_velocity       double,
  avg_spin_rate          double,
  pitch_count            bigint,
  usage_rate             double,

  -- partition column
  season                 int
)
PARTITIONED BY (season)
LOCATION 's3://{lakehouse_bucket}/gold/gold_pitches_shape_season/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
