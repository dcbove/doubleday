-- gold_pitches_shape_season: per-pitcher, per-pitch-type season aggregations
-- Rebuilt from silver_pitches via partition overwrite on (season)
CREATE TABLE IF NOT EXISTS gold_pitches_shape_season (
  pitcher                bigint,
  pitch_type             string,

  -- Movement (inches). Horizontal is normalized so "glove-side" is positive.
  avg_horz_break_in      double,
  avg_vert_break_in      double,
  stddev_horz_break_in   double,
  stddev_vert_break_in   double,
  p10_horz_break_in      double,
  p90_horz_break_in      double,
  p10_vert_break_in      double,
  p90_vert_break_in      double,

  -- Velocity
  avg_velocity           double,
  p10_velocity           double,
  p90_velocity           double,

  -- Extension-adjusted velocity
  avg_adj_velocity       double,

  -- Spin
  avg_spin_rate          double,

  -- Counts / usage
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
